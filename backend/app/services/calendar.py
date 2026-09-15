"""Calendar — 오늘 실제로 몇 분이 비었는가.

학교 시간표를 가져오지 않는다. 직접 넣는다.

여기서 조심할 것이 하나 있다.
**"수업이 없는 시간" 은 "공부할 수 있는 시간" 이 아니다.**
9시간이 비어도 9시간 공부하지 않는다. 그래서 빈 시간을 그대로
오늘 계획의 예산으로 쓰지 않고, 사용자가 정한 하루 상한과 비교해
**작은 쪽**을 제안한다.

시각은 자정 기준 분이다. 문자열 시간을 파싱하는 대신 빼기만 하면
되고, 겹침 판정도 정수 비교로 끝난다.
"""

from datetime import date, datetime, timedelta

from .. import models
from . import profile as profile_service

KINDS = ("class", "work", "personal", "fixed", "deadline")

KIND_LABELS = {
    "class": "수업",
    "work": "일 · 알바",
    "personal": "개인 일정",
    "fixed": "고정",
    "deadline": "마감",
}

DAY_MINUTES = 24 * 60


def format_minute(value: int) -> str:
    """자정 기준 분을 09:30 꼴로."""
    return f"{value // 60:02d}:{value % 60:02d}"


def serialize(block) -> dict:
    return {
        "id": block.id,
        "title": block.title,
        "kind": block.kind,
        "kind_label": KIND_LABELS.get(block.kind, block.kind),
        "weekday": block.weekday,
        "date": block.date,
        "repeats": block.weekday is not None,
        "all_day": bool(block.all_day),
        "start_minute": block.start_minute,
        "end_minute": block.end_minute,
        "start": format_minute(block.start_minute),
        "end": format_minute(block.end_minute),
        "minutes": block.end_minute - block.start_minute,
        "note": block.note,
    }


def list_blocks(db, weekday=None) -> list[dict]:
    query = db.query(models.CalendarBlock)

    if weekday is not None:
        query = query.filter(models.CalendarBlock.weekday == weekday)

    blocks = query.order_by(
        models.CalendarBlock.start_minute,
        models.CalendarBlock.id,
    ).all()

    return [serialize(block) for block in blocks]


def blocks_for(db, day: date):
    """그날 실제로 걸리는 일정 — 매주 반복 + 그날짜 일회성."""
    return (
        db.query(models.CalendarBlock)
        .filter(
            (models.CalendarBlock.weekday == day.weekday())
            | (models.CalendarBlock.date == day)
        )
        .order_by(models.CalendarBlock.start_minute)
        .all()
    )


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """겹치는 일정을 합친다.

    수업과 알바가 겹쳐 있으면 두 번 빼게 되고, 그러면 비어 있는
    시간이 실제보다 적게 나온다.
    """
    merged: list[list[int]] = []

    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    return [(start, end) for start, end in merged]


def takes_time(block) -> bool:
    """이 일정이 그날의 시간을 먹는가.

    마감은 그날 할 일이 아니라 그날까지의 선이다. 종일 일정(시험 기간,
    학회)도 몇 시부터 몇 시까지 막히는지 모른다. 둘 다 빈 시간에서
    빼면 하루가 통째로 사라진다.
    """
    return not block.all_day and block.kind != "deadline"


def _budget(profile, blocks) -> dict:
    """활동 시간대 − 일정 = 빈 시간 → 상한과 비교한 제안."""
    window_start = profile.day_start_minute
    window_end = profile.day_end_minute
    window = max(0, window_end - window_start)

    # 활동 시간대 밖의 일정은 세지 않는다.
    # 새벽 알바를 빼면 낮에 쓸 시간이 줄어든 것처럼 보인다.
    clipped = [
        (max(block.start_minute, window_start), min(block.end_minute, window_end))
        for block in blocks
        if takes_time(block)
    ]
    clipped = [(start, end) for start, end in clipped if end > start]

    busy = sum(end - start for start, end in _merge(clipped))
    free = max(0, window - busy)

    return {
        "window_minutes": window,
        "busy_minutes": busy,
        "free_minutes": free,
        # 빈 시간을 그대로 쓰지 않는다. 상한과 비교해 작은 쪽.
        "suggested_minutes": min(free, profile.daily_cap_minutes),
    }


def _window_label(profile) -> str:
    return (
        f"{format_minute(profile.day_start_minute)}–"
        f"{format_minute(profile.day_end_minute)}"
    )


def build_day(db, day: date | None = None) -> dict:
    """오늘 몇 분이 비었고, 그중 얼마를 쓰자고 제안하는가."""
    day = day or date.today()

    profile = profile_service.get_profile(db)
    blocks = blocks_for(db, day)
    budget = _budget(profile, blocks)

    return {
        "date": day,
        "weekday": day.weekday(),
        "window_start": profile.day_start_minute,
        "window_end": profile.day_end_minute,
        "window_label": _window_label(profile),
        "daily_cap_minutes": profile.daily_cap_minutes,
        **budget,
        "capped": budget["suggested_minutes"] < budget["free_minutes"],
        "blocks": [serialize(block) for block in blocks],
        "note": (
            "빈 시간을 그대로 쓰지 않습니다. "
            "하루 상한과 비교해 작은 쪽을 제안합니다."
        ),
    }


def build_week(db, start: date | None = None) -> dict:
    """요일별 일정과 빈 시간. 매주 반복되는 것만."""
    profile = profile_service.get_profile(db)

    days = []

    for weekday in range(7):
        blocks = (
            db.query(models.CalendarBlock)
            .filter(models.CalendarBlock.weekday == weekday)
            .order_by(models.CalendarBlock.start_minute)
            .all()
        )

        budget = _budget(profile, blocks)

        days.append({
            "weekday": weekday,
            "busy_minutes": budget["busy_minutes"],
            "free_minutes": budget["free_minutes"],
            "suggested_minutes": budget["suggested_minutes"],
            "blocks": [serialize(block) for block in blocks],
        })

    return {
        "window_start": profile.day_start_minute,
        "window_end": profile.day_end_minute,
        "window_label": _window_label(profile),
        "daily_cap_minutes": profile.daily_cap_minutes,
        "days": days,
        # 일회성 일정은 주간 격자에 넣지 않는다.
        # 매주 반복되는 것처럼 보이면 거짓이다.
        "note": "매주 반복되는 일정만 표시합니다. 하루짜리는 그날에만 걸립니다.",
    }


# --------------------------------
# 한 달
#
# 요일 격자만으로는 "다음 주 목요일에 뭐가 있지?" 를 답할 수 없었다.
# 하루짜리 일정은 격자에 안 뜨고, 공고 마감은 다른 화면에 있었다.
# 달력 한 장에 셋을 같이 놓는다 — 매주 일정, 하루 일정, 마감.
# --------------------------------

def _as_date(value):
    return value.date() if isinstance(value, datetime) else value


def _posting_deadlines(db, first: date, last: date) -> dict:
    """이 기간에 걸린 지원서·공고 마감을 날짜별로.

    오늘 D-day 띠(today.collect_deadlines)와 같은 규칙이다 — 철회한
    지원서는 빼고, 지원서가 있는 공고는 공고 쪽에서 다시 세지 않는다.
    다만 여기는 지나간 마감도 보여준다. 달력은 지난 날도 보는 곳이다.
    """
    by_day: dict = {}
    covered = set()

    applications = (
        db.query(models.Application)
        .filter(models.Application.deadline.isnot(None))
        .all()
    )

    for application in applications:
        if application.opportunity_id is not None:
            covered.add(application.opportunity_id)

        if application.status == "withdrawn":
            continue

        day = _as_date(application.deadline)

        if not first <= day <= last:
            continue

        posting = application.opportunity or application.legacy_job

        by_day.setdefault(day, []).append({
            "kind": "application",
            "id": application.id,
            "title": getattr(posting, "title", None) or "지원서",
            "organization": (
                getattr(posting, "organization", None)
                or getattr(posting, "company", None)
                or ""
            ),
            "status": application.status,
        })

    opportunities = (
        db.query(models.Opportunity)
        .filter(models.Opportunity.deadline.isnot(None))
        .filter(models.Opportunity.status.in_(("interested", "preparing")))
        .all()
    )

    for opportunity in opportunities:
        if opportunity.id in covered:
            continue

        day = _as_date(opportunity.deadline)

        if not first <= day <= last:
            continue

        by_day.setdefault(day, []).append({
            "kind": "opportunity",
            "id": opportunity.id,
            "title": opportunity.title,
            "organization": opportunity.organization or "",
            "status": opportunity.status,
            # 달력이 "공고 마감" 과 "채용 행사" 를 가르게.
            "opportunity_type": opportunity.opportunity_type,
        })

    return by_day


def build_month(db, year: int, month: int) -> dict:
    """월요일부터 일요일까지 꽉 채운 주 단위 격자."""
    profile = profile_service.get_profile(db)

    first_of_month = date(year, month, 1)
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    last_of_month = next_month - timedelta(days=1)

    first = first_of_month - timedelta(days=first_of_month.weekday())
    last = last_of_month + timedelta(days=6 - last_of_month.weekday())

    weekly = (
        db.query(models.CalendarBlock)
        .filter(models.CalendarBlock.weekday.isnot(None))
        .all()
    )
    one_off = (
        db.query(models.CalendarBlock)
        .filter(models.CalendarBlock.date >= first)
        .filter(models.CalendarBlock.date <= last)
        .all()
    )
    deadlines = _posting_deadlines(db, first, last)

    today = date.today()
    days = []
    day = first

    while day <= last:
        blocks = [b for b in weekly if b.weekday == day.weekday()]
        blocks += [b for b in one_off if b.date == day]

        # 마감 → 종일 → 시간순. 칸이 좁아서 위에 있는 것만 보인다.
        blocks.sort(
            key=lambda b: (b.kind != "deadline", not b.all_day, b.start_minute, b.id)
        )

        days.append({
            "date": day,
            "day": day.day,
            "weekday": day.weekday(),
            "in_month": day.month == month,
            "is_today": day == today,
            "blocks": [serialize(block) for block in blocks],
            "deadlines": deadlines.get(day, []),
            **_budget(profile, blocks),
        })

        day += timedelta(days=1)

    return {
        "year": year,
        "month": month,
        "today": today,
        "window_label": _window_label(profile),
        "daily_cap_minutes": profile.daily_cap_minutes,
        "weeks": [days[i:i + 7] for i in range(0, len(days), 7)],
    }
