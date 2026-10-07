"""시장 신호 - Mission 023.

Mission 022 까지는 레거시 `Job` 만 세었고 추세를 계산할 수 없었다.
시점별 값이 없으면 "올랐다/내렸다" 를 말할 방법이 없기 때문이다.

이제 수집이 끝날 때마다 스킬별 수요를 한 줄씩 남기고(MarketSnapshot),
직전 스냅샷과 비교해 추세를 낸다.

**통계는 반드시 저장된 실제 데이터에서 계산한다. 지어내지 않는다.**
"""

from datetime import date, datetime

from .. import models


# 수요로 세지 않는 공고 상태. 사람이 "안 간다" 고 내린 것들이다.
DEMAND_OFF_STATUS = ("not_interested", "closed", "archived")

# 수요로 세지 않는 종류.
#
# `job_event` 는 채용 박람회 · 행사다 — 지자체 일자리박람회, 잡페스타 같은 것.
# 공고가 아니라 "이런 자리가 있다" 는 안내라서 모집 직무도 요구 역량도 없다.
# 수집할 때 이미 종류를 나눠 저장하고 있었는데(work24_event 수집원), 수요를
# 셀 때는 안 가렸다. 108건 중 17건이 이것이었고, 전부 스킬이 하나도 안 붙은
# 채로 **분모**에만 들어갔다. 그만큼 모든 스킬의 수요 비율이 낮게 나왔다.
DEMAND_OFF_TYPES = ("job_event",)


# 이 값보다 작은 변화는 추세로 보지 않는다.
# 공고 몇 건 차이로 화살표가 요동치는 걸 막는다.
TREND_THRESHOLD_POINTS = 3

TREND_UP = "up"
TREND_DOWN = "down"
TREND_FLAT = "flat"
TREND_UNKNOWN = "unknown"


def demand_opportunities(db, today: date | None = None) -> list:
    """수요로 세는 공고. **분자와 분모가 같은 모집단을 써야 한다.**

    전에는 모수만 걸렀고 스킬별 건수(분자)는 전부 셌다. 그래서 비율이
    모집단이 다른 두 수의 나눗셈이었다.

    세지 않는 것 셋 —
      1. 직무가 달라 자동으로 뺀 것 (job_fit)
         영업 · 생산 공고가 들어가면 모든 스킬의 비율이 까닭 없이 내려간다.
      2. **마감이 지난 것** — 지원할 수 없는 공고는 지금의 수요가 아니다.
         실제로 "지금 가장 중요한 스킬" 이 이미 끝난 공고들에서 나오고 있었다.
      3. 사람이 내린 것 (관심 없음 · 보관함 · 닫음)
         CJ 계열사 제한처럼 "갈 수 없다" 고 정한 공고는 내 수요가 아니다.
      4. **채용 박람회 · 행사** (job_event) — 공고가 아니다.
         모집 직무가 없어 요구 역량도 없다. 분모만 불린다.
      5. **지원 자격이 안 되는 것** (blocked_reason) — 석사 필수처럼
         사람이 "나는 못 쓴다" 고 정한 것. 마감 지난 것과 같은 까닭이다.
         실제로 Reinforcement Learning 수요 4건이 **전부** 석박사 자리였다.

    마감이 없는 공고(상시채용)는 센다 — 아직 열려 있다.
    """
    today = today or date.today()

    rows = (
        db.query(models.Opportunity)
        .filter(models.Opportunity.filtered_reason == "")
        .filter(models.Opportunity.blocked_reason == "")
        .filter(~models.Opportunity.status.in_(DEMAND_OFF_STATUS))
        .filter(~models.Opportunity.opportunity_type.in_(DEMAND_OFF_TYPES))
        .all()
    )

    live = []
    for row in rows:
        deadline = row.deadline
        if isinstance(deadline, datetime):
            deadline = deadline.date()
        if deadline is not None and deadline < today:
            continue
        live.append(row)

    return live


def blocked_by_skill(db) -> list[dict]:
    """자격 때문에 못 쓰는 공고가 스킬마다 몇 건인가.

    지우지 않고 세어 두는 까닭이 이것이다. "Computer Vision 공고 4건 중
    3건이 석사 요구" 를 말할 수 있어야, 그 스킬을 공부할지 말지를 정할 수
    있다. 삭제하면 그 신호까지 사라진다.

    분모는 **쓸 수 있는 것 + 막힌 것** 이다. 쓸 수 있는 것만 세면 "4건 중
    3건" 의 4가 나오지 않는다.
    """
    blocked = (
        db.query(models.Opportunity)
        .filter(models.Opportunity.blocked_reason != "")
        .filter(models.Opportunity.filtered_reason == "")
        .filter(~models.Opportunity.opportunity_type.in_(DEMAND_OFF_TYPES))
        .all()
    )

    if not blocked:
        return []

    open_ids = {row.id for row in demand_opportunities(db)}
    blocked_ids = {row.id for row in blocked}

    rows = []

    for skill in db.query(models.Skill).all():
        linked = {row.id for row in skill.opportunities}

        stopped = len(linked & blocked_ids)

        if not stopped:
            continue

        total = len(linked & (open_ids | blocked_ids))

        rows.append({
            "skill": skill.name,
            "skill_id": skill.id,
            "blocked": stopped,
            "total": total,
            "percentage": round(stopped / total * 100) if total else 0,
            # 왜 막혔는지. 같은 까닭이 여러 번이면 한 번만.
            "reasons": sorted({
                row.blocked_reason for row in blocked if row.id in linked
            }),
        })

    # 비중이 큰 것부터 — "이 스킬은 거의 다 막혀 있다" 가 먼저 보여야 한다.
    rows.sort(key=lambda item: (-item["percentage"], -item["blocked"]))

    return rows


def count_opportunities(db) -> int:
    """수요의 모수."""
    return len(demand_opportunities(db))


def build_signals(db) -> list[dict]:
    """스킬별 현재 수요. 저장하지 않는다."""
    skills = db.query(models.Skill).all()
    live = demand_opportunities(db)
    counted = {row.id for row in live}
    total = len(live)

    signals = []

    for skill in skills:
        # 분모와 같은 모집단에서만 센다.
        count = sum(1 for row in skill.opportunities if row.id in counted)

        percentage = round(count / total * 100) if total else 0

        signals.append({
            "skill": skill.name,
            "skill_id": skill.id,
            "opportunity_count": count,
            "percentage": percentage,
            "my_level": skill.level or 0,
        })

    signals.sort(key=lambda item: item["opportunity_count"], reverse=True)

    return signals


def capture_snapshot(db) -> int:
    """현재 수요를 스냅샷으로 남긴다. 저장한 행 수를 돌려준다.

    수집이 끝날 때마다 호출한다.
    """
    total = count_opportunities(db)

    if total == 0:
        # 기회가 하나도 없으면 남길 신호가 없다.
        return 0

    rows = []

    for skill in db.query(models.Skill).all():
        count = len(skill.opportunities)

        rows.append(models.MarketSnapshot(
            skill_id=skill.id,
            opportunity_count=count,
            total_opportunities=total,
            percentage=round(count / total * 100),
        ))

    db.add_all(rows)
    db.commit()

    return len(rows)


def recent_snapshots(db, skill_id, limit: int = 2) -> list:
    """이 스킬의 최근 스냅샷을 새 것부터.

    `captured_at` 이 아니라 id 순으로 본다.
    SQLite 의 CURRENT_TIMESTAMP 는 초 단위라 같은 초에 저장된
    스냅샷끼리는 시간으로 순서를 가릴 수 없기 때문이다.
    스냅샷은 append 만 되므로 id 순서가 곧 기록 순서다.
    """
    return (
        db.query(models.MarketSnapshot)
        .filter(models.MarketSnapshot.skill_id == skill_id)
        .order_by(models.MarketSnapshot.id.desc())
        .limit(limit)
        .all()
    )


def _trend(current, previous):
    if previous is None:
        return TREND_UNKNOWN, None

    delta = current - previous

    if abs(delta) < TREND_THRESHOLD_POINTS:
        return TREND_FLAT, delta

    return (TREND_UP if delta > 0 else TREND_DOWN), delta


def build_signals_with_trend(db, limit: int | None = None) -> dict:
    """현재 수요 + 직전 스냅샷 대비 추세.

    스냅샷이 하나뿐이면 추세는 `unknown` 이다.
    비교할 과거가 없는데 화살표를 그리지 않는다.
    """
    total = count_opportunities(db)

    signals = []

    for signal in build_signals(db):
        # 추세는 기록된 스냅샷 두 개를 비교해서 낸다.
        # 라이브 값과 스냅샷을 섞어 비교하면 수집 시점에 따라 값이 튄다.
        snapshots = recent_snapshots(db, signal["skill_id"], limit=2)

        current = (
            snapshots[0].percentage if snapshots else None
        )
        previous = (
            snapshots[1].percentage if len(snapshots) > 1 else None
        )

        if current is None:
            trend, delta = TREND_UNKNOWN, None
        else:
            trend, delta = _trend(current, previous)

        signals.append({
            **signal,
            "trend": trend,
            "change_points": delta,
            "snapshot_percentage": current,
            "previous_percentage": previous,
        })

    if limit is not None:
        signals = signals[:limit]

    snapshot_count = db.query(models.MarketSnapshot).count()

    return {
        "total_opportunities": total,
        "source_count": db.query(
            models.Opportunity.source
        ).distinct().count(),
        "snapshot_count": snapshot_count,
        "has_trend_data": snapshot_count > 0 and any(
            signal["previous_percentage"] is not None
            for signal in signals
        ),
        "signals": signals,
    }
