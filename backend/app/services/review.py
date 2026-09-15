"""기간 회고 — "이번 달에 뭘 쌓았나".

하루치로는 아무것도 안 보인다. 오늘 45분 공부한 것은 그 자체로는
의미를 못 만든다. 한 달을 모아야 "이걸 배웠다" 가 된다.

데이터는 이미 매일 기록되고 있었다. 세그먼트·학습 단계·오늘 태스크에
completed_at 이 있고, 경험·포트폴리오·공고·지원에 시각이 있다.
모아서 보여주는 곳만 없었다.

**세지 못하는 것은 세지 않는다.** projects 에는 시각이 없어서
"이번 달에 프로젝트를 끝냈다" 는 아직 계산할 수 없다. 그걸 그럴듯하게
지어내면 회고 전체가 못 믿을 것이 된다.

스킬 레벨은 skill_level_events 가 생기면서 셀 수 있게 됐다.
그 전의 변화는 기록이 없으므로 없는 것으로 둔다 — 소급해서
지어내지 않는다.
"""

from calendar import monthrange
from datetime import date, datetime

from .. import models


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """그 달의 시작과 끝. 끝은 마지막 날 23:59:59 까지 포함한다."""
    last = monthrange(year, month)[1]

    return (
        datetime(year, month, 1),
        datetime(year, month, last, 23, 59, 59),
    )


def _in_period(column, start: datetime, end: datetime):
    return column.isnot(None), column >= start, column <= end


def _skill_of_segment(segment) -> str | None:
    resource = segment.resource

    return resource.skill.name if resource and resource.skill else None


def _skill_of_step(step) -> str | None:
    path = step.learning_path

    return path.skill.name if path and path.skill else None


def _execution(db, start: datetime, end: datetime, today: date) -> dict:
    """계획 대비 실행. 오늘 이후 아직 안 한 것은 분모에 넣지 않는다."""
    tasks = (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.plan_date >= start.date())
        .filter(models.DailyPlanTask.plan_date <= end.date())
        .all()
    )

    by_area: dict[str, dict] = {}

    done = skipped = missed = pending = 0

    for task in tasks:
        row = by_area.setdefault(task.task_type, {"done": 0, "not_done": 0})

        if task.status == "done":
            done += 1
            row["done"] += 1
        elif task.status == "skipped":
            skipped += 1
            row["not_done"] += 1
        elif task.plan_date < today:
            missed += 1
            row["not_done"] += 1
        else:
            pending += 1

    decided = done + skipped + missed

    return {
        "planned": len(tasks),
        "done": done,
        "skipped": skipped,
        "missed": missed,
        "pending": pending,
        "decided": decided,
        "rate": round(done / decided * 100) if decided else None,
        "by_area": by_area,
    }


def _postponed(db, start: datetime, end: datetime) -> list[dict]:
    """반복해서 이월된 일. 같은 제목이 여러 날 넘어온 횟수로 센다."""
    tasks = (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.plan_date >= start.date())
        .filter(models.DailyPlanTask.plan_date <= end.date())
        .filter(models.DailyPlanTask.carried_from.isnot(None))
        .all()
    )

    groups: dict[str, dict] = {}

    for task in tasks:
        row = groups.setdefault(
            task.title, {"title": task.title, "times": 0, "first_planned": task.carried_from}
        )
        row["times"] += 1
        row["first_planned"] = min(row["first_planned"], task.carried_from)

    rows = sorted(groups.values(), key=lambda row: (-row["times"], row["title"]))

    return [
        {**row, "first_planned": row["first_planned"].isoformat()}
        for row in rows[:5]
    ]


# 다음 달에 바꿀 것 — 규칙으로만 고른다. 근거가 되는 숫자를 같이 준다.
# 기록이 이 문턱보다 적으면 말하지 않는다. 계획 두 개로 "실행률 0%" 를
# 문제 삼으면 잔소리가 된다.
MIN_DECIDED_FOR_RATE = 5
LOW_RATE = 50
REPEATED_POSTPONE = 3
PROJECT_MISSES = 3


def _next_month(execution: dict, postponed: list[dict]) -> list[dict]:
    if execution["planned"] == 0:
        return [{
            "title": "오늘 계획을 세우면 회고가 쌓여요",
            "evidence": "이 달에는 오늘 계획 기록이 없어요.",
            "route": "today",
        }]

    suggestions = []

    if (
        execution["rate"] is not None
        and execution["decided"] >= MIN_DECIDED_FOR_RATE
        and execution["rate"] < LOW_RATE
    ):
        suggestions.append({
            "title": "하루 계획을 줄여 보세요",
            "evidence": (
                f"지난 날까지 계획한 {execution['decided']}개 중 "
                f"{execution['done']}개를 끝냈어요 ({execution['rate']}%). "
                "하루 상한을 낮추면 끝낼 수 있는 만큼만 계획돼요."
            ),
            "route": "calendar",
        })

    if postponed and postponed[0]["times"] >= REPEATED_POSTPONE:
        top = postponed[0]
        suggestions.append({
            "title": f"'{top['title']}' — 쪼개거나 계획에서 빼 보세요",
            "evidence": f"이 달에 {top['times']}번 이월됐어요.",
            "route": "today",
        })

    project = execution["by_area"].get("project")

    if (
        project
        and project["not_done"] >= PROJECT_MISSES
        and project["not_done"] >= project["done"]
    ):
        total = project["done"] + project["not_done"]
        suggestions.append({
            "title": "프로젝트 작업을 더 작게 나눠 보세요",
            "evidence": f"프로젝트 작업 {total}개 중 {project['not_done']}개를 끝내지 못했어요.",
            "route": "projects",
        })

    return suggestions


def serialize_reflection(row) -> dict | None:
    if row is None:
        return None
    return {
        "rating": row.rating,
        "went_well": row.went_well,
        "to_improve": row.to_improve,
        "next_focus": row.next_focus,
        "updated_at": row.updated_at,
    }


def get_reflection(db, year: int, month: int):
    return (
        db.query(models.MonthlyReflection)
        .filter_by(year=year, month=month)
        .one_or_none()
    )


def save_reflection(db, year: int, month: int, payload) -> dict:
    """그 달의 스스로 평가를 적는다. 없으면 만들고 있으면 고친다."""
    row = get_reflection(db, year, month)
    if row is None:
        row = models.MonthlyReflection(year=year, month=month)
        db.add(row)

    row.rating = payload.rating
    row.went_well = payload.went_well.strip()
    row.to_improve = payload.to_improve.strip()
    row.next_focus = payload.next_focus.strip()

    db.commit()
    db.refresh(row)
    return serialize_reflection(row)


def build_review(db, year: int, month: int, today: date | None = None) -> dict:
    """그 달에 실제로 쌓인 것."""
    today = today or date.today()
    start, end = month_bounds(year, month)

    execution = _execution(db, start, end, today)
    postponed = _postponed(db, start, end)

    segments = (
        db.query(models.LearningResourceSegment)
        .filter(*_in_period(
            models.LearningResourceSegment.completed_at, start, end
        ))
        .all()
    )

    steps = (
        db.query(models.LearningStep)
        .filter(*_in_period(models.LearningStep.completed_at, start, end))
        .all()
    )

    tasks = (
        db.query(models.DailyPlanTask)
        .filter(
            models.DailyPlanTask.status == "done",
            *_in_period(models.DailyPlanTask.completed_at, start, end),
        )
        .all()
    )

    level_events = (
        db.query(models.SkillLevelEvent)
        .filter(*_in_period(models.SkillLevelEvent.changed_at, start, end))
        .order_by(models.SkillLevelEvent.changed_at)
        .all()
    )

    experiences = (
        db.query(models.Experience)
        .filter(*_in_period(models.Experience.created_at, start, end))
        .all()
    )

    portfolio = (
        db.query(models.PortfolioEntry)
        .filter(*_in_period(models.PortfolioEntry.created_at, start, end))
        .count()
    )

    collected = (
        db.query(models.Opportunity)
        .filter(*_in_period(models.Opportunity.collected_at, start, end))
        .count()
    )

    applied = (
        db.query(models.Application)
        .filter(*_in_period(models.Application.applied_at, start, end))
        .count()
    )

    # 스킬별로 묶는다. "45분 공부했다" 보다 "Machine Learning 에
    # 90분을 썼고 2챕터를 끝냈다" 가 쌓인 것을 말해준다.
    by_skill: dict[str, dict] = {}

    def bucket(name: str) -> dict:
        return by_skill.setdefault(
            name, {"skill": name, "segments": 0, "steps": 0, "minutes": 0}
        )

    for segment in segments:
        name = _skill_of_segment(segment)

        if name:
            bucket(name)["segments"] += 1

    for step in steps:
        name = _skill_of_step(step)

        if name:
            bucket(name)["steps"] += 1

    for task in tasks:
        name = _task_skill(db, task)

        if name:
            bucket(name)["minutes"] += task.minutes or 0

    ranked = sorted(
        by_skill.values(),
        key=lambda row: (row["segments"] + row["steps"], row["minutes"]),
        reverse=True,
    )

    return {
        "period": {
            "year": year,
            "month": month,
            "label": f"{year}년 {month}월",
            "from": start.date().isoformat(),
            "to": end.date().isoformat(),
        },
        "learning": {
            "segments_done": len(segments),
            "steps_done": len(steps),
            "tasks_done": len(tasks),
            "minutes": sum(task.minutes or 0 for task in tasks),
            "by_skill": ranked,
        },
        "evidence": {
            "experiences": len(experiences),
            "portfolio_entries": portfolio,
        },
        # 이 달에 실제로 오른(또는 내린) 스킬.
        # 한 스킬이 여러 번 움직였으면 처음과 끝만 남긴다 —
        # 0→1→2 는 "0에서 2로" 한 줄이면 된다.
        "levels": _level_moves(level_events),
        "market": {
            "opportunities_collected": collected,
            "applications_sent": applied,
        },
        "done": [
            {
                "kind": "segment",
                "title": f"{segment.resource.title} — {segment.label}"
                if segment.resource
                else segment.label,
                "skill": _skill_of_segment(segment),
                "at": segment.completed_at.date().isoformat(),
            }
            for segment in sorted(
                segments, key=lambda item: item.completed_at
            )
        ]
        + [
            {
                "kind": "step",
                "title": step.title,
                "skill": _skill_of_step(step),
                "at": step.completed_at.date().isoformat(),
            }
            for step in sorted(steps, key=lambda item: item.completed_at)
        ],
        # 계획 대비 실행 · 반복해서 미룬 일 · 다음 달에 바꿀 것.
        "execution": execution,
        "postponed": postponed,
        "next_month": _next_month(execution, postponed),
        # 기록이 말해주지 않는 것 — 사람이 적은 한 달 평가. 없으면 None.
        "reflection": serialize_reflection(get_reflection(db, year, month)),
        # 지금 세지 못하는 것을 화면이 알 수 있게 밝힌다.
        # projects 에는 시각이 없어서 완료 시점을 만들 수 없다.
        "not_tracked": ["project_completion_date"],
    }


def _level_moves(events) -> list[dict]:
    """한 스킬의 여러 변화를 처음과 끝으로 접는다.

    0 → 1 → 2 를 두 줄로 보여주면 "두 번 올랐다" 로 읽힌다.
    실제로 일어난 일은 "0에서 2가 되었다" 하나다.
    """
    folded: dict[int, dict] = {}

    for event in events:
        row = folded.get(event.skill_id)

        if row is None:
            folded[event.skill_id] = {
                "skill": event.skill.name if event.skill else None,
                "from": event.from_level,
                "to": event.to_level,
                "at": event.changed_at.date().isoformat(),
            }
        else:
            row["to"] = event.to_level
            row["at"] = event.changed_at.date().isoformat()

    # 제자리로 돌아온 것은 변화가 아니다 (0 → 1 → 0).
    return [
        row
        for row in folded.values()
        if row["from"] != row["to"]
    ]


def _task_skill(db, task) -> str | None:
    """오늘 태스크가 어느 스킬의 일이었나.

    태스크는 스킬을 직접 가리키지 않는다. 가리키는 대상을 따라간다.
    """
    if task.learning_step_id:
        step = db.get(models.LearningStep, task.learning_step_id)

        return _skill_of_step(step) if step else None

    if task.learning_resource_id:
        resource = db.get(
            models.LearningResource, task.learning_resource_id
        )

        return resource.skill.name if resource and resource.skill else None

    if task.project_id:
        project = db.get(models.Project, task.project_id)

        if project and project.skills:
            return project.skills[0].name

    return None


def recent_months(db, count: int = 6, today: date | None = None) -> list[dict]:
    """최근 몇 달의 요약. 추세를 보려면 한 달로는 부족하다."""
    today = today or date.today()

    months = []
    year, month = today.year, today.month

    for _ in range(count):
        months.append(build_review(db, year, month))

        month -= 1

        if month == 0:
            year, month = year - 1, 12

    return months


def _bucket(count: int) -> int:
    """칸 색의 진하기. 0 · 1 · 2~3 · 4 이상."""
    if count <= 0:
        return 0
    if count == 1:
        return 1
    if count <= 3:
        return 2
    return 3


def build_activity(db, year: int, month: int) -> dict:
    """그 달의 날마다 끝낸 것. Review 의 잔디 칸이 이걸로 칠해진다.

    시간(분)이 아니라 개수로 센다. 분은 오늘 할 일을 완료할 때만
    남아서, 챕터를 따로 끝낸 날이 0분으로 보인다.

    같은 일을 두 번 세지 않는다. 학습 단계에 딸린 할 일을 완료하면
    그 단계도 함께 완료 처리되므로(today.complete_task), 그런 할 일은
    빼고 단계 쪽으로 센다.
    """
    start, end = month_bounds(year, month)
    days: dict[str, list[dict]] = {}

    def add(when, kind, title):
        days.setdefault(when.date().isoformat(), []).append(
            {"kind": kind, "title": title}
        )

    for segment in (
        db.query(models.LearningResourceSegment)
        .filter(*_in_period(models.LearningResourceSegment.completed_at, start, end))
    ):
        title = (
            f"{segment.resource.title} — {segment.label}"
            if segment.resource else segment.label
        )
        add(segment.completed_at, "segment", title)

    for step in (
        db.query(models.LearningStep)
        .filter(*_in_period(models.LearningStep.completed_at, start, end))
    ):
        add(step.completed_at, "step", step.title)

    for task in (
        db.query(models.DailyPlanTask)
        .filter(
            models.DailyPlanTask.status == "done",
            models.DailyPlanTask.learning_step_id.is_(None),
            *_in_period(models.DailyPlanTask.completed_at, start, end),
        )
    ):
        add(task.completed_at, "task", task.title)

    for event in (
        db.query(models.SkillLevelEvent)
        .filter(*_in_period(models.SkillLevelEvent.changed_at, start, end))
    ):
        name = event.skill.name if event.skill else "스킬"
        add(event.changed_at, "level", f"{name} 레벨 {event.from_level} → {event.to_level}")

    grid = []
    for day in range(1, monthrange(year, month)[1] + 1):
        key = date(year, month, day).isoformat()
        items = days.get(key, [])
        grid.append({
            "date": key,
            "count": len(items),
            "level": _bucket(len(items)),
            "items": items,
        })

    return {
        "period": {"year": year, "month": month, "label": f"{year}년 {month}월"},
        "days": grid,
        "active_days": sum(1 for d in grid if d["count"]),
        "total": sum(d["count"] for d in grid),
    }
