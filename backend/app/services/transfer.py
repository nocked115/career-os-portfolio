"""로컬과 배포본 사이에서 데이터를 통째로 옮긴다.

엔티티마다 내보내기를 손으로 짜지 않는다. 테이블이 19개에 연결
테이블이 6개고, 새 테이블이 생길 때마다 하나씩 빠뜨리게 된다.
대신 메타데이터를 읽어 전부 덤프하고, 기본키를 그대로 살려서
넣는다. 그래야 외래키와 연결 테이블이 저절로 맞는다.

이건 이사용이면서 백업용이다. 볼륨 위의 SQLite 파일 하나를
꺼내올 방법이 없으면, 그 볼륨을 지우는 순간 경력 기록이 사라진다.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import Date, DateTime, Time, func, select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from .. import models  # noqa: F401
from ..database import Base

# 파일 형식이 바뀌면 올린다. 옛 파일을 조용히 잘못 읽는 것보다
# 못 읽겠다고 하는 편이 낫다.
FORMAT_VERSION = 1


class TransferError(ValueError):
    """옮길 수 없는 파일. 호출자가 400 으로 바꿔 돌려준다."""


def schema_revision(db: Session) -> str | None:
    """Alembic 이 기록해둔 현재 리비전."""
    try:
        row = db.execute(
            text("select version_num from alembic_version")
        ).first()
    except DatabaseError:
        # 마이그레이션을 한 번도 안 돌린 DB (테스트에서 그렇다).
        return None

    return row[0] if row else None


def _tables():
    """의존성 순서. 부모가 먼저 온다.

    metadata 는 모델 모듈을 임포트해야 채워진다. 위에서 models 를
    임포트하는 이유가 그것이다. 그게 없으면 여기가 빈 목록을
    돌려주고, 내보내기는 성공했다면서 빈 파일을 만든다.
    백업 도구에서 그보다 나쁜 실패는 없다.
    """
    tables = list(Base.metadata.sorted_tables)

    if not tables:
        raise TransferError(
            "테이블 메타데이터가 비어 있습니다. "
            "모델이 임포트되지 않았습니다."
        )

    return tables


def _encode(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()

    return value


def _decode(value: Any, column) -> Any:
    if value is None:
        return None

    # JSON 에는 날짜가 없다. 컬럼 타입을 보고 되돌린다.
    # 이걸 안 하면 문자열이 그대로 들어가서, 넣을 때는 조용하고
    # 나중에 날짜 비교하는 곳에서 터진다.
    kind = column.type

    if isinstance(kind, DateTime):
        return dt.datetime.fromisoformat(value)

    if isinstance(kind, Date):
        return dt.date.fromisoformat(value)

    if isinstance(kind, Time):
        return dt.time.fromisoformat(value)

    return value


# 쌓이기만 하고 사람이 고치지 않는 기록.
#
# 스케줄러가 매일 한 줄씩 붙인다. 로컬 파일에는 그 뒤로 쌓인 줄이
# 없으므로, 대체하면 서버에서 쌓인 날들이 통째로 사라진다. 실제로
# 두 번 났다 — 25 → 6, 82 → 6.
#
# "받아온 뒤 고친다" 는 규칙으로 막으려 했지만 두 번 다 지켜지지
# 않았다. 규칙이 아니라 코드로 막는다: 이 테이블들은 파일에 없는
# 줄을 지우지 않고 남긴다. 기본키가 다시 쓰이지 않는 append-only
# 기록이라 합쳐도 부딪히지 않는다.
APPEND_ONLY_TABLES = ("market_snapshots",)


# 사람이 실제로 무언가 한 흔적이 남는 자리.
#
# 스케줄러가 매일 건드리는 것(market_snapshots, opportunities.scored_at)
# 은 넣지 않는다. 그것까지 세면 아무것도 안 해도 항상 "새 작업이
# 있다" 가 되어 경고가 늑대 소년이 된다.
ACTIVITY_COLUMNS = (
    ("daily_plan_tasks", "completed_at"),
    ("learning_resource_segments", "completed_at"),
    ("learning_steps", "completed_at"),
    ("skill_level_events", "changed_at"),
    ("experiences", "updated_at"),
    ("portfolio_entries", "updated_at"),
    ("applications", "updated_at"),
)


def latest_activity(db: Session) -> dt.datetime | None:
    """이 DB 에서 사람이 마지막으로 무언가 한 시각."""
    newest = None

    for table_name, column_name in ACTIVITY_COLUMNS:
        table = Base.metadata.tables.get(table_name)

        if table is None or column_name not in table.c:
            continue

        found = db.execute(
            select(func.max(table.c[column_name]))
        ).scalar()

        if found is None:
            continue

        if isinstance(found, str):
            found = dt.datetime.fromisoformat(found)

        if newest is None or found > newest:
            newest = found

    return newest


def payload_activity(payload: dict[str, Any]) -> dt.datetime | None:
    """이 파일이 담고 있는 마지막 작업 시각.

    latest_activity 와 같은 자리를 본다. 파일과 DB 를 같은 잣대로
    재야 "이 파일이 저쪽 작업을 담고 있는가" 를 물을 수 있다.
    """
    tables = payload.get("tables") or {}
    newest = None

    for table_name, column_name in ACTIVITY_COLUMNS:
        for row in tables.get(table_name) or []:
            value = row.get(column_name)

            if not value:
                continue

            found = dt.datetime.fromisoformat(value)

            if newest is None or found > newest:
                newest = found

    return newest


def dump(db: Session) -> dict[str, Any]:
    """모든 테이블을 그대로 뜬다."""
    tables = {
        table.name: [
            {key: _encode(value) for key, value in row.items()}
            for row in db.execute(table.select()).mappings().all()
        ]
        for table in _tables()
    }

    return {
        "format": FORMAT_VERSION,
        "schema_revision": schema_revision(db),
        "exported_at": dt.datetime.now().isoformat(timespec="seconds"),
        "tables": tables,
    }


def counts(payload: dict[str, Any]) -> dict[str, int]:
    """빈 테이블은 빼고 센다. 사람이 눈으로 확인하는 용도다."""
    return {
        name: len(rows)
        for name, rows in payload.get("tables", {}).items()
        if rows
    }


class StaleFile(TransferError):
    """받는 쪽에 이 파일보다 새로운 작업이 있다.

    덮어쓰면 그 작업이 사라진다. 다른 오류와 구분해야 호출자가
    "강제로 진행" 을 물어볼 수 있다.
    """


def load(
    db: Session,
    payload: dict[str, Any],
    *,
    allow_schema_mismatch: bool = False,
    allow_stale: bool = False,
) -> dict[str, Any]:
    """덤프로 현재 데이터를 통째로 대체한다.

    합치지 않는다. 합치면 같은 ID 를 가진 다른 레코드가 부딪히고,
    무엇이 남고 무엇이 덮였는지 아무도 모르게 된다.
    """
    if not isinstance(payload, dict) or "tables" not in payload:
        raise TransferError(
            "내보내기 파일이 아닙니다 (tables 키가 없습니다)."
        )

    if payload.get("format") != FORMAT_VERSION:
        raise TransferError(
            f"파일 형식 {payload.get('format')!r} 은 읽을 수 없습니다 "
            f"(이 서버는 {FORMAT_VERSION})."
        )

    # 스키마가 어긋난 채로 넣으면 컬럼 하나가 조용히 빠진다.
    # 그게 지운 것보다 나쁘다 — 지운 건 알아채기라도 한다.
    here = schema_revision(db)
    there = payload.get("schema_revision")

    if here != there and not allow_schema_mismatch:
        raise TransferError(
            f"스키마 리비전이 다릅니다 (이 서버 {here}, 파일 {there}). "
            "양쪽을 같은 커밋으로 맞춘 뒤 다시 시도하세요."
        )

    # 이 파일이 받는 쪽의 작업을 담고 있는가.
    #
    # 로컬과 배포본은 서로를 모른다. 배포본에서 챕터를 완료하고
    # 레벨을 올린 뒤 그것이 없는 로컬 파일을 올리면, 그 작업이
    # 통째로 사라진다. 되돌릴 방법도 없다.
    #
    # **exported_at 으로 재면 안 된다.** 그건 "파일을 언제 떴나"
    # 일 뿐, 파일이 저쪽 작업을 담고 있는지와 무관하다. 실제로
    # 한 번 그대로 통과했다 — 배포본에서 14:30 에 한 일이 있는데,
    # 로컬에서 14:40 에 뜬 파일이라 최신으로 보였다.
    #
    # 파일 안의 마지막 작업과 잰다. 같은 잣대여야 답이 맞는다.
    if not allow_stale:
        here = latest_activity(db)

        if here is not None:
            mine = payload_activity(payload)

            if mine is None or here > mine:
                had = (
                    f"파일 {mine:%Y-%m-%d %H:%M}"
                    if mine
                    else "파일에는 작업 기록이 없습니다"
                )

                raise StaleFile(
                    f"받는 쪽에 이 파일에 없는 작업이 있습니다 "
                    f"({had}, 서버 {here:%Y-%m-%d %H:%M}). "
                    "그대로 올리면 그 작업이 사라집니다. "
                    "먼저 서버에서 export 로 받아오세요."
                )

    known = {table.name: table for table in _tables()}
    unknown = sorted(set(payload["tables"]) - set(known))

    if unknown:
        raise TransferError(f"모르는 테이블입니다: {unknown}")

    for name, rows in payload["tables"].items():
        columns = {column.name for column in known[name].columns}
        extra = sorted({key for row in rows for key in row} - columns)

        if extra:
            raise TransferError(f"{name} 에 모르는 컬럼입니다: {extra}")

    # 지우기 전에 무엇을 지우는지 센다. 응답에 그대로 돌려줘서
    # 엉뚱한 서버에 쏜 것을 바로 알아볼 수 있게 한다.
    # SELECT 의 rowcount 는 -1 을 돌려주기도 한다. 세는 건 세서 센다.
    counted = {
        table.name: db.execute(
            select(func.count()).select_from(table)
        ).scalar_one()
        for table in _tables()
    }
    replaced = {
        name: count for name, count in counted.items() if count
    }

    # 쌓이기만 하는 기록 중 파일에 없는 줄을 지우기 전에 떠둔다.
    survivors: dict[str, list[dict]] = {}

    for table in _tables():
        if table.name not in APPEND_ONLY_TABLES:
            continue

        incoming = {
            row.get("id") for row in payload["tables"].get(table.name) or []
        }

        survivors[table.name] = [
            dict(row)
            for row in db.execute(table.select()).mappings().all()
            if row["id"] not in incoming
        ]

    # 자식부터 지운다.
    for table in reversed(_tables()):
        db.execute(table.delete())

    written: dict[str, int] = {}

    for table in _tables():
        rows = payload["tables"].get(table.name) or []

        if not rows:
            continue

        columns = {column.name: column for column in table.columns}

        db.execute(
            table.insert(),
            [
                {
                    key: _decode(value, columns[key])
                    for key, value in row.items()
                }
                for row in rows
            ],
        )

        written[table.name] = len(rows)

    kept: dict[str, int] = {}

    for table in _tables():
        rows = survivors.get(table.name) or []

        if rows:
            db.execute(table.insert(), rows)
            kept[table.name] = len(rows)

    db.commit()

    # SQLite 는 rowid 최대값 + 1 로 다음 ID 를 잡으므로, 명시적으로
    # 넣은 ID 뒤부터 이어진다. 시퀀스를 따로 고칠 게 없다.
    # PostgreSQL 로 옮기면 여기서 setval 이 필요하다.
    return {"replaced": replaced, "written": written, "kept": kept}
