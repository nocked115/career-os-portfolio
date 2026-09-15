"""Profile — 화면 가운데 있어야 할 사람.

Career OS 는 1인용이라 로그인도 사용자 목록도 없다. 그래서 지금까지
사용자를 나타내는 것이 아무것도 없었고, 화면이 전부 남의 대시보드처럼
읽혔다 (DESIGN.md 3장).

주간 누적 시간은 새로 기록하지 않는다. 완료한 계획 항목이 이미
plan_date 와 minutes 를 갖고 있어서 그것을 더하면 된다.

한계가 하나 있고, 숨기지 않는다 — **계획을 통해 한 일만 센다.**
계획 밖에서 한 공부는 여기 잡히지 않는다.
"""

from datetime import date, timedelta

from .. import models
from . import priority as priority_service

WEEK_DAYS = 7


def get_profile(db) -> models.Profile:
    """단 하나의 프로필. 없으면 만든다.

    빈 이름으로 만든다. 이름을 지어내지 않는다.
    """
    profile = db.query(models.Profile).order_by(models.Profile.id).first()

    if profile is None:
        profile = models.Profile(name="")
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return profile


def update_profile(db, name: str | None = None, **links) -> models.Profile:
    """보낸 것만 바꾼다. name=None 이면 이름은 그대로 둔다."""
    profile = get_profile(db)

    if name is not None:
        profile.name = name.strip()

    for field in ("github_url", "blog_url"):
        if links.get(field) is not None:
            setattr(profile, field, links[field].strip())

    db.commit()
    db.refresh(profile)

    return profile


def weekly_effort(db, today: date | None = None) -> dict:
    """최근 7일 동안 실제로 끝낸 것.

    계획에서 done 으로 표시한 항목만 센다. 그 밖의 공부는 모른다.
    """
    today = today or date.today()
    since = today - timedelta(days=WEEK_DAYS - 1)

    tasks = (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.status == "done")
        .filter(models.DailyPlanTask.plan_date >= since)
        .filter(models.DailyPlanTask.plan_date <= today)
        .all()
    )

    minutes = sum(task.minutes for task in tasks)

    return {
        "since": since,
        "until": today,
        "minutes": minutes,
        "hours": minutes // 60,
        "remainder_minutes": minutes % 60,
        "completed_tasks": len(tasks),
        "active_days": len({task.plan_date for task in tasks}),
        "note": (
            "계획에서 완료한 것만 셉니다. "
            "계획 밖에서 한 공부는 포함되지 않습니다."
        ),
    }


def build_profile(db, today: date | None = None) -> dict:
    """화면 가운데에 놓을 것 — 나, 내 방향, 이번 주.

    focus 는 우선순위 서비스에서 그대로 가져온다.
    여기서 다시 계산하지 않는다.
    """
    profile = get_profile(db)
    target = priority_service.get_active_target_career(db)

    entries = priority_service.build_skill_priorities(db)
    focus = entries[0] if entries else None

    return {
        "name": profile.name,
        "has_name": bool(profile.name),
        "github_url": profile.github_url,
        "blog_url": profile.blog_url,
        "target_career": target.title if target else None,
        "focus_skill": focus["skill_name"] if focus else None,
        "priority_score": focus["priority_score"] if focus else None,
        "week": weekly_effort(db, today),
    }
