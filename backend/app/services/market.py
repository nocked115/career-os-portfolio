"""시장 신호 - Mission 023.

Mission 022 까지는 레거시 `Job` 만 세었고 추세를 계산할 수 없었다.
시점별 값이 없으면 "올랐다/내렸다" 를 말할 방법이 없기 때문이다.

이제 수집이 끝날 때마다 스킬별 수요를 한 줄씩 남기고(MarketSnapshot),
직전 스냅샷과 비교해 추세를 낸다.

**통계는 반드시 저장된 실제 데이터에서 계산한다. 지어내지 않는다.**
"""

from .. import models


# 이 값보다 작은 변화는 추세로 보지 않는다.
# 공고 몇 건 차이로 화살표가 요동치는 걸 막는다.
TREND_THRESHOLD_POINTS = 3

TREND_UP = "up"
TREND_DOWN = "down"
TREND_FLAT = "flat"
TREND_UNKNOWN = "unknown"


def count_opportunities(db) -> int:
    """수요의 모수. 직무가 달라 자동으로 뺀 공고는 세지 않는다 (job_fit).

    영업 · 생산 공고가 모수에 들어가면 모든 스킬의 비율이 까닭 없이 내려간다.
    """
    return (
        db.query(models.Opportunity)
        .filter(models.Opportunity.filtered_reason == "")
        .count()
    )


def build_signals(db) -> list[dict]:
    """스킬별 현재 수요. 저장하지 않는다."""
    skills = db.query(models.Skill).all()
    total = count_opportunities(db)

    signals = []

    for skill in skills:
        count = len(skill.opportunities)

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
