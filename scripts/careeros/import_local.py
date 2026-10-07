"""내보낸 파일을 **이 노트북의** 데이터베이스에 넣는다.

  python3 import_local.py ~/Documents/career-os/backups/career-os-production-....json

서버를 안 띄우고 SQLite 파일을 직접 연다. 배포본을 거치지 않으므로
비밀번호도 필요 없다 — 배포본은 건드리지 않는다.

**기존 로컬 데이터를 전부 지우고 대체한다.** 무엇이 들어오고 무엇이
사라지는지 보여주고 한 번 물어본다.

Railway Trial 이 끝나면 이 노트북이 원본이 된다. 순서는:
  1. scripts/careeros/export_production.py   배포본 → 파일
  2. scripts/careeros/import_local.py <파일>  파일 → 이 노트북
  3. bash scripts/local.sh                    띄우기
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

# 프로젝트의 파이썬으로 돌린다.
#
# 시스템 python3 로 실행해도 anaconda 에 sqlalchemy 가 있으면 import 는 되는데,
# alembic 버전이 다르거나 아예 없을 수 있다. 앱의 DB 를 건드리는 스크립트는
# 앱과 같은 환경에서 돌아야 한다.
VENV_BIN = BACKEND / ".venv" / "bin"
VENV_PYTHON = VENV_BIN / "python"

if VENV_PYTHON.is_file() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

# 앱과 같은 코드로 읽고 쓴다. 스키마 검사 · 오래된 파일 검사를 그대로 쓰려는 것이다.
os.environ.setdefault("CAREER_OS_DATABASE_URL", f"sqlite:///{BACKEND / 'career_os.db'}")
sys.path.insert(0, str(BACKEND))

from app.database import SessionLocal  # noqa: E402
from app.services import transfer as transfer_service  # noqa: E402


def _alembic(*args) -> None:
    """alembic 을 **별도 프로세스로** 돌린다.

    import 로 쓸 수 없다. 이 스크립트는 `app.*` 을 쓰려고 sys.path 에
    backend 를 넣는데, 거기에 `backend/alembic/` **폴더**(마이그레이션이
    들어 있는 곳)가 있다. __init__.py 가 없어서 파이썬이 이걸 namespace
    package 로 잡고, 설치된 alembic 라이브러리를 가린다:

        ImportError: cannot import name 'command' from 'alembic'
                     (unknown location)

    local.sh 와 Dockerfile 도 명령줄로 돌린다. 같은 방식으로 맞춘다.
    """
    executable = VENV_BIN / "alembic"

    if not executable.is_file():
        # 시스템 파이썬(anaconda 등)에는 alembic 이 없는 게 보통이다.
        # 여기서 `python -m alembic` 로 넘기면 ModuleNotFoundError 가
        # 나는데, 그걸 보고 무엇을 해야 할지는 알 수 없다.
        sys.exit(
            "프로젝트 파이썬 환경이 없어요.\n"
            "  먼저 한 번 만들어 주세요:\n"
            f"    python3 -m venv {BACKEND / '.venv'}\n"
            f"    {VENV_BIN / 'pip'} install -r {BACKEND / 'requirements.txt'}\n"
            "  (bash scripts/local.sh 가 이걸 자동으로 합니다.)"
        )

    command = [str(executable)]

    result = subprocess.run(
        [*command, *args],
        cwd=BACKEND,                       # alembic.ini 의 상대 경로가 여기 기준이다
        env={**os.environ, "CAREER_OS_DATABASE_URL": os.environ["CAREER_OS_DATABASE_URL"]},
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        sys.exit(
            "스키마를 맞추지 못했어요.\n"
            + (result.stderr or result.stdout).strip()
        )


def _upgrade_schema() -> None:
    """이 노트북의 DB 를 코드와 같은 스키마로 올린다.

    **먼저 해야 한다.** 안 하면 아래에서 "지금 뭐가 들었나" 를 보여주려고
    DB 를 읽는 순간 터진다 — 코드가 아는 테이블이 옛 DB 에는 없기 때문이다.
    실제로 났다: 로컬이 0033_log_learned 에 멈춰 있어서
    `no such table: preferred_companies` 로 죽었다.

    배포본 Dockerfile 의 CMD 와 같은 일이다 — 뜰 때마다 alembic 을 먼저 돌린다.
    """
    _alembic("upgrade", "head")


def _is_ancestor(old_revision: str) -> bool:
    """파일의 리비전이 이 코드가 아는 것인가.

    마이그레이션 파일을 직접 훑는다. alembic 을 import 할 수 없어서다
    (`_alembic` 의 주석 참고).

    이 코드의 versions/ 에 그 리비전이 있고 지금 head 가 아니라면, 역사가
    선형이므로 **조상**이다. 그 뒤로 앞으로만 갔다는 뜻이고 칸은 늘기만
    했다 — 넣어도 안전하고, 새 칸은 기본값으로 채워진다.

    반대 방향(파일이 코드보다 새것)이면 여기서 못 찾는다. 그때는 칸이
    사라졌을 수 있으므로 사람에게 묻는다.
    """
    versions = BACKEND / "alembic" / "versions"

    if not versions.is_dir():
        return False

    needle = re.compile(
        r"^revision(?::\s*str)?\s*=\s*['\"]" + re.escape(old_revision) + r"['\"]",
        re.MULTILINE,
    )

    return any(
        needle.search(path.read_text(encoding="utf-8"))
        for path in versions.glob("*.py")
    )


def _load(db, payload):
    """넣는다. 막히면 **왜** 막혔는지 보고 사람에게 묻는다.

    두 가지로 막힌다. 둘 다 기본값은 "안 함" 이다 — 되돌릴 수 없다.

    1. 스키마 리비전이 다름. 옛날에 뜬 파일이면 반드시 걸린다.
       (실제로 9/28 백업은 0034_prefs 에서 떴고 코드는 0035_portfolio 다.)
       컬럼이 늘기만 했으면 넣어도 된다 — 없는 칸은 기본값으로 남는다.
       **줄어든 경우에는 그 칸의 내용이 사라진다.**
    2. 받는 쪽에 이 파일에 없는 작업이 있음(오래된 파일).
    """
    try:
        return transfer_service.load(db, payload)
    except transfer_service.StaleFile as error:
        print(f"\n멈췄어요 — {error}")
        answer = input(
            "그래도 덮어쓸까요? 이 노트북의 더 새로운 작업이 사라집니다. 'YES': "
        ).strip()
        if answer != "YES":
            sys.exit("그만뒀어요. 아무것도 안 바뀌었습니다.")
        return transfer_service.load(db, payload, allow_stale=True)
    except transfer_service.TransferError as error:
        if "스키마 리비전" not in str(error):
            sys.exit(f"\n넣지 못했어요 — {error}")

        file_revision = str(payload.get("schema_revision") or "")

        # 파일이 코드의 **옛 버전**에서 떴다면 묻지 않는다. 그 사이의
        # 마이그레이션이 앞으로만 갔다는 뜻이고, 칸은 늘기만 했으므로
        # 새 칸이 기본값으로 채워질 뿐이다. 사람이 판단할 일이 아니다.
        #
        # (실제로 났다 — export 와 import 사이에 0036_track 이 들어가서,
        #  안전한 경우인데도 "내용이 사라집니다" 라고 겁주고 있었다.)
        if file_revision and _is_ancestor(file_revision):
            print(
                f"\n파일은 {file_revision} 에서 떴고 지금 코드는 그보다 뒤예요. "
                "그 사이 늘어난 칸은 기본값으로 채웁니다 — 그대로 넣을게요."
            )
            return transfer_service.load(db, payload, allow_schema_mismatch=True)

        # 반대 방향이거나 알 수 없는 리비전. 칸이 사라졌을 수 있다.
        print(f"\n멈췄어요 — {error}")
        print(
            "  파일의 리비전을 이 코드에서 못 찾았어요. 파일이 코드보다 **새것**\n"
            "  이라면 지금 없는 칸의 내용이 사라집니다. 먼저 git pull 을 해보세요."
        )
        answer = input("그래도 넣을까요? 'YES': ").strip()
        if answer != "YES":
            sys.exit("그만뒀어요. 아무것도 안 바뀌었습니다.")
        return transfer_service.load(db, payload, allow_schema_mismatch=True)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    path = Path(sys.argv[1]).expanduser()

    if not path.is_file():
        sys.exit(f"그런 파일이 없어요: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))

    print("이 노트북의 스키마를 코드에 맞추는 중…")
    _upgrade_schema()

    incoming = transfer_service.counts(payload)

    if not incoming:
        sys.exit("파일이 비어 있어요. 빈 파일로 덮어쓰지 않습니다.")

    print(f"넣을 파일: {path}")
    print(f"  뜬 시각 {payload.get('exported_at', '모름')}")
    print("  담긴 것 —")
    for name, count in sorted(incoming.items(), key=lambda kv: -kv[1]):
        print(f"    {name:34} {count:>6}")

    db = SessionLocal()

    try:
        # 정보성이다. 여기서 터져 아무것도 못 하게 되는 일이 없게 한다.
        try:
            current = transfer_service.counts(transfer_service.dump(db))
        except Exception as error:  # noqa: BLE001
            print(f"\n지금 들어 있는 것은 못 읽었어요 ({type(error).__name__}).")
            print("  넣는 데는 지장이 없지만, 무엇이 사라지는지는 안 보입니다.")
            current = None

        print(f"\n지금 이 노트북({os.environ['CAREER_OS_DATABASE_URL']}) —")
        if current is None:
            print("    (못 읽음)")
        elif current:
            for name, count in sorted(current.items(), key=lambda kv: -kv[1]):
                print(f"    {name:34} {count:>6}")
            print("\n  ** 위의 것이 전부 지워지고 파일 내용으로 바뀝니다. **")
        else:
            print("    (비어 있음)")

        answer = input("\n진행할까요? 'REPLACE' 라고 적으세요: ").strip()

        if answer != "REPLACE":
            sys.exit("그만뒀어요. 아무것도 안 바뀌었습니다.")

        result = _load(db, payload)
    finally:
        db.close()

    print("\n넣었어요.")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print("\n이제 띄우면 됩니다:  bash scripts/local.sh")


if __name__ == "__main__":
    main()
