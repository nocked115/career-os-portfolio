"""오늘의 계획 - Phase 1.

Career OS 의 북극성은 "오늘 무엇을 할 것인가" 다.
Todo 앱과의 차이는 사용자가 할 일을 넣는 게 아니라
**시스템이 여러 정보를 보고 결정한다**는 점이다.

    학습 우선순위 + 학습 진행 + 프로젝트 진행
        + 마감 + 가용 시간 + 강도
            → Today Plan

계획을 저장하는 이유는 완료 체크와 미완료 이월 때문이다.
매번 새로 계산해서 버리면 둘 다 할 수 없다.
"""

from datetime import date, datetime, timedelta

from .. import models
from . import checklist as checklist_service
from . import learning as learning_service
from . import routine as routine_service
from . import priority as priority_service


# --------------------------------
# 강도
#
# 같은 120분이어도 어떻게 쓸지는 다르다.
# 가벼운 날은 짧게 여러 개, 몰입하는 날은 길게 적게.
# --------------------------------

INTENSITY = {
    "light": {
        "max_tasks": 2,
        "max_block": 30,
        "min_block": 10,
        "label": "가볍게",
    },
    "normal": {
        "max_tasks": 3,
        "max_block": 60,
        "min_block": 15,
        "label": "보통",
    },
    "deep_focus": {
        "max_tasks": 2,
        "max_block": 120,
        "min_block": 45,
        "label": "몰입",
    },
}

DEFAULT_INTENSITY = "normal"
DEFAULT_AVAILABLE_MINUTES = 120

# 이 안에 마감이 있으면 오늘 계획에 올린다.
DEADLINE_HORIZON_DAYS = 14

# 마감이 이보다 가까우면 다른 것보다 먼저 놓는다.
DEADLINE_URGENT_DAYS = 3


def get_intensity(name: str | None) -> dict:
    return INTENSITY.get(name or DEFAULT_INTENSITY, INTENSITY[DEFAULT_INTENSITY])


# --------------------------------
# 마감
# --------------------------------

def _days_left(deadline, today):
    if deadline is None:
        return None

    value = deadline.date() if isinstance(deadline, datetime) else deadline

    return (value - today).days


def collect_deadlines(db, today: date | None = None) -> list[dict]:
    """다가오는 마감. 지난 것은 빼고, 가까운 순으로.

    지원서와 기회 양쪽을 본다.
    """
    today = today or date.today()

    items = []

    # 지원서가 이미 있는 기회는 아래에서 다시 세지 않는다.
    # 같은 공고가 "지원 준비" 와 "지원할지 정하기" 로 두 번 뜬다 —
    # 마감 띠에도 두 줄, 오늘 계획에도 두 칸을 차지한다.
    #
    # 지원서가 더 진행된 상태이므로 그쪽을 남긴다. "없는 지원서를
    # 준비할 수 없다" 의 반대쪽이다 — 이미 만든 지원서를 두고
    # "지원할지 정하기" 를 말할 이유도 없다.
    covered = set()

    applications = (
        db.query(models.Application)
        .filter(models.Application.deadline.isnot(None))
        .all()
    )

    for application in applications:
        # 철회·지원 완료한 지원서도 그 공고를 "이미 정한 것" 으로 덮는다.
        # 여기서 먼저 빠지면 같은 공고가 기회 마감으로 다시 뜬다.
        if application.opportunity_id is not None:
            covered.add(application.opportunity_id)

        if application.status in ("applied", "rejected", "accepted", "withdrawn"):
            continue

        days = _days_left(application.deadline, today)

        if days is None or days < 0 or days > DEADLINE_HORIZON_DAYS:
            continue

        title = "지원서"

        if application.opportunity is not None:
            title = application.opportunity.title
            covered.add(application.opportunity_id)
        elif application.legacy_job is not None:
            title = application.legacy_job.title

        items.append({
            "kind": "application",
            "id": application.id,
            "title": title,
            "status": application.status,
            "days_left": days,
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

        days = _days_left(opportunity.deadline, today)

        if days is None or days < 0 or days > DEADLINE_HORIZON_DAYS:
            continue

        items.append({
            "kind": "opportunity",
            "id": opportunity.id,
            "title": opportunity.title,
            "status": opportunity.status,
            # 채용 행사는 지원하는 공고가 아니라 가는 날이다. 문구를 가르려면 종류가 필요하다.
            "opportunity_type": opportunity.opportunity_type,
            "days_left": days,
        })

    # 달력에 넣은 마감 — 캡스톤 발표, 논문 제출. 공고가 아니어도
    # 날짜는 선이다. 띠에는 띄우지만 할 일로는 만들지 않는다 —
    # 그날까지 무엇을 준비해야 하는지 앱은 모른다.
    events = (
        db.query(models.CalendarBlock)
        .filter(models.CalendarBlock.kind == "deadline")
        .filter(models.CalendarBlock.date.isnot(None))
        .all()
    )

    for block in events:
        days = _days_left(block.date, today)

        if days < 0 or days > DEADLINE_HORIZON_DAYS:
            continue

        items.append({
            "kind": "event",
            "id": block.id,
            "title": block.title,
            "status": "deadline",
            "days_left": days,
        })

    items.sort(key=lambda item: item["days_left"])

    return items


# --------------------------------
# 후보 만들기
# --------------------------------

# 이월에 수명을 준다.
#
# 사흘 넘게 밀어둔 일은 사실 안 할 일일 가능성이 높다. 그런데 이월은
# 계획의 앞자리를 차지하므로, 그대로 두면 오늘 가장 중요한 일이 영영
# 계획에 못 들어간다.
#
# 실제로 그랬다 — 수요 0/3 인 스킬의 작업 셋이 사흘째 세 칸을 다
# 차지하는 동안, 수요 3/3 인 1위 스킬은 한 번도 올라오지 못했다.
# 그 계획들은 진짜 공고를 넣기 전에 짜인 것이었고, 우선순위가 바뀌어도
# 이월은 다시 검사되지 않았다.
#
# 조용히 버리지는 않는다. 후보에서 빼고 "이건 안 할 건가요?" 라고 묻는다.
CARRY_OVER_LIMIT_DAYS = 3


def _leftover_tasks(db, today: date):
    """어제까지 못 끝낸 것. 최근 것부터, 같은 대상은 한 번만."""
    tasks = (
        db.query(models.DailyPlanTask)
        .filter(
            models.DailyPlanTask.plan_date < today,
            models.DailyPlanTask.status == "planned",
            # 루틴은 이월하지 않는다. 어제 못 한 코테를 오늘 두 번 하게 두지 않는다.
            models.DailyPlanTask.routine_id.is_(None),
        )
        .order_by(
            models.DailyPlanTask.plan_date.desc(),
            models.DailyPlanTask.position,
        )
        .all()
    )

    unique = []
    seen = set()

    for task in tasks:
        key = (task.task_type, task.learning_step_id, task.project_id,
               task.learning_resource_id, task.application_id, task.title)

        if key in seen:
            continue

        seen.add(key)
        unique.append(task)

    return unique


def _carried_days(task, today: date) -> int:
    """처음 계획한 날로부터 며칠이 지났는가."""
    origin = task.carried_from or task.plan_date

    return (today - origin).days


def _carry_over_candidates(db, today: date) -> list[dict]:
    """어제까지 못 끝낸 것. 사라지지 않고 오늘로 넘어온다.

    단, 수명을 넘긴 것은 빠진다 (stale_carry_overs 가 대신 묻는다).
    """
    candidates = []

    for task in _leftover_tasks(db, today):
        if _carried_days(task, today) > CARRY_OVER_LIMIT_DAYS:
            continue

        candidates.append({
            "task_type": task.task_type,
            "title": task.title,
            "minutes": task.minutes,
            "reason": f"{task.plan_date.isoformat()} 에 계획했지만 끝내지 못했습니다.",
            "carried_from": task.carried_from or task.plan_date,
            "learning_step_id": task.learning_step_id,
            "project_id": task.project_id,
            "learning_resource_id": task.learning_resource_id,
            "application_id": task.application_id,
            "urgent": False,
        })

    return candidates


def stale_carry_overs(db, today: date | None = None) -> list[dict]:
    """수명이 다한 이월. 계획에 올리지 않고 물어본다.

    화면은 이걸로 "이건 안 할 건가요?" 를 띄운다. 사람이 치우거나
    (skip) 다시 하겠다고 하면 그때 계획에 돌아온다.
    """
    today = today or date.today()

    return [
        {
            "task_id": task.id,
            "title": task.title,
            "task_type": task.task_type,
            "minutes": task.minutes,
            "first_planned": (task.carried_from or task.plan_date).isoformat(),
            "days_carried": _carried_days(task, today),
        }
        for task in _leftover_tasks(db, today)
        if _carried_days(task, today) > CARRY_OVER_LIMIT_DAYS
    ]


def _deadline_candidates(db, today: date) -> list[dict]:
    """마감이 임박한 것.

    지원서를 이미 만든 것과 아직 안 만든 기회를 둘 다 본다.
    전에는 지원서만 봤기 때문에, 마감이 내일인 공고를 넣어도
    오늘 계획에 아무것도 안 올라왔다.

    둘은 할 일이 다르다. 지원서가 있으면 "준비" 지만, 없으면
    아직 "지원할지 정하기" 다. 없는 지원서를 준비할 수는 없다.
    """
    candidates = []

    for item in collect_deadlines(db, today):
        if item["days_left"] > DEADLINE_URGENT_DAYS:
            continue

        if item["kind"] == "application":
            candidates.append({
                "task_type": "application",
                "title": f"지원 준비 — {item['title']}",
                "minutes": 30,
                "reason": f"{_due_text(item['days_left'])}.",
                "application_id": item["id"],
                "urgent": True,
            })
            continue

        if item["kind"] == "opportunity" and item.get("opportunity_type") == "job_event":
            days = item["days_left"]
            candidates.append({
                "task_type": "opportunity",
                "title": f"참석할지 정하기 — {item['title']}",
                "minutes": 15,
                "reason": "오늘 열리는 채용 행사입니다." if days == 0 else f"채용 행사까지 {days}일 남았습니다.",
                "opportunity_id": item["id"],
                "urgent": True,
            })
            continue

        if item["kind"] == "opportunity":
            candidates.append({
                "task_type": "opportunity",
                "title": f"지원할지 정하기 — {item['title']}",
                "minutes": 15,
                "reason": (
                    f"{_due_text(item['days_left'])}. "
                    "아직 지원서를 만들지 않았습니다."
                ),
                "opportunity_id": item["id"],
                "urgent": True,
            })

    return candidates


def _skill_reason(entry, tail: str | None = None) -> str:
    """왜 이 스킬인가를 사람이 읽는 문장으로.

    전에는 "(점수 87)" 을 붙였다. 87 이 무엇의 87 인지 화면에서는 알 수
    없었다. 점수를 만든 재료 — 모아둔 기회 중 몇 건이 요구하는지, 지금
    레벨이 몇인지 — 를 분모와 함께 쓴다.
    """
    skill = entry["skill"]

    parts = []

    if entry.get("total_demand"):
        parts.append(
            f"모아둔 기회 {entry['total_demand']}건 중 "
            f"{entry['demand_count']}건이 요구"
        )

    # 지도(opportunity_map)는 skill 과 점수만 넘긴다. 레벨은 스킬에서 읽는다.
    level = entry.get("my_level", skill.level or 0)

    parts.append(f"지금 레벨 {level}/{priority_service.MAX_SKILL_LEVEL}")

    sentence = (
        f"{skill.name} 이(가) 학습 우선순위 1위입니다 — "
        + " · ".join(parts)
        + "."
    )

    return f"{sentence} {tail}" if tail else sentence


def _learning_candidate(db, entry) -> dict | None:
    """우선순위 1위 스킬의 다음 학습 단계."""
    skill = entry["skill"]

    step = learning_service.find_next_step(skill)

    if step is not None:
        return {
            "task_type": "learning_step",
            "title": step.title,
            "minutes": step.estimated_minutes or 30,
            "reason": (
                _skill_reason(entry)
            ),
            "learning_step_id": step.id,
            "urgent": False,
        }

    # 계획에 올릴 수 있는 것을 먼저 고른다.
    #
    # 전에는 skill.resources[0] 을 그냥 집었다. 그래서 13챕터로
    # 쪼개둔 MySQL 강좌를 두고, 분량도 모르는 자료가 앞에 있다는
    # 이유로 "30분" 이라는 지어낸 숫자를 내놓았다. 쪼개는 일이
    # 계획에 아무 영향을 주지 못했다.
    #
    # 순서: 쪼개둔 것 → 길이를 아는 것 → 나머지.
    # 앞의 둘은 오늘 몇 분인지 말할 수 있고, 마지막은 못 한다.
    def plannable(resource) -> int:
        if any(item.status != "completed" for item in resource.segments):
            return 0

        if (resource.duration_minutes or 0) > 0:
            return 1

        return 2

    for resource in sorted(
        (r for r in skill.resources if r.status != "completed"),
        key=plannable,
    ):
        # 자료를 쪼개뒀으면 그 조각이 오늘의 단위다.
        # "책 한 권을 읽으세요" 가 아니라 "3장을 45분" 이어야 한다
        # (LearningResourceSegment 의 존재 이유).
        segment = next(
            (
                item
                for item in resource.segments
                if item.status != "completed"
            ),
            None,
        )

        if segment is not None:
            return {
                "task_type": "resource",
                "title": f"{resource.title} — {segment.label}",
                "minutes": segment.estimated_minutes or 30,
                "reason": (
                    _skill_reason(entry)
                ),
                "learning_resource_id": resource.id,
                "urgent": False,
            }

        return {
            "task_type": "resource",
            "title": resource.title,
            "minutes": resource.duration_minutes or 30,
            "reason": (
                _skill_reason(entry, "아직 학습 경로가 없어 자료를 바로 씁니다.")
            ),
            "learning_resource_id": resource.id,
            "urgent": False,
        }

    return None


# 마감이 있는 학습은 하루에 둘까지.
MAX_DUE_LEARNING = 2


def _due_text(days: int) -> str:
    if days < 0:
        return f"마감이 {-days}일 지났습니다"
    if days == 0:
        return "오늘 마감입니다"
    return f"마감까지 {days}일 남았습니다"


def _due_learning_candidates(db, today: date) -> list[dict]:
    """마감이 있는 학습 — 우선순위 1위 스킬이 아니어도 올라온다.

    전에는 학습 후보가 우선순위 1위 스킬의 다음 단계 하나뿐이었다. 그래서
    이번 주말에 발표할 논문 주차도, 마감이 있는 스프린트도 스킬 순위가
    낮으면 오늘 계획에 한 번도 오르지 않았다.

    단계에 마감일(due_date)이 있으면 그 단계를, 경로에 목표일(target_date)만
    있으면 그 경로의 다음 단계를 본다. 14일 안에 들어온 것만.
    """
    horizon = today + timedelta(days=DEADLINE_HORIZON_DAYS)
    found = []

    steps = (
        db.query(models.LearningStep)
        .filter(
            models.LearningStep.status != learning_service.COMPLETED,
            models.LearningStep.due_date.isnot(None),
            models.LearningStep.due_date <= horizon,
        )
        .all()
    )
    for step in steps:
        found.append((step.due_date, step))

    paths = (
        db.query(models.LearningPath)
        .filter(
            models.LearningPath.status != learning_service.COMPLETED,
            models.LearningPath.target_date.isnot(None),
            models.LearningPath.target_date <= horizon,
        )
        .all()
    )
    for path in paths:
        step = routine_service.next_step(path)
        if step is not None and step.due_date is None:
            found.append((path.target_date, step))

    found.sort(key=lambda row: (row[0], row[1].position))

    candidates = []
    seen = set()

    for due, step in found:
        if step.id in seen:
            continue
        seen.add(step.id)

        days = (due - today).days
        path = step.learning_path
        summary = checklist_service.summary(step)
        tail = (
            f" 체크 {summary['total']}개 중 {summary['done']}개 했습니다."
            if summary
            else ""
        )

        candidates.append({
            "task_type": "learning_step",
            "title": f"{path.title} — {step.title}",
            "minutes": step.estimated_minutes or 45,
            "reason": f"{_due_text(days)}.{tail}",
            "learning_step_id": step.id,
            "days_left": days,
            "urgent": days <= DEADLINE_URGENT_DAYS,
        })

        if len(candidates) >= MAX_DUE_LEARNING:
            break

    return candidates


# 하루에 프로젝트를 셋 넣으면 아무것도 안 끝난다.
MAX_PROJECT_CANDIDATES = 2


def _parse_target_date(value):
    """Project.target_date 는 자유 문자열이다. 못 읽으면 없는 셈 친다."""
    if not value:
        return None

    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _project_candidates(db, entries, today: date) -> list[dict]:
    """진행 중인 커리어 프로젝트.

    전에는 우선순위 1위 스킬의 프로젝트만 후보가 됐다. 그런데
    프로젝트를 붙이는 것 자체가 그 스킬의 점수를 낮추기 때문에,
    **프로젝트를 등록하면 그 프로젝트가 오늘 계획에서 사라지는**
    일이 생겼다.

    프로젝트가 있다는 사실은 "그 스킬을 새로 배울 필요" 는 낮추지만
    "그 프로젝트를 끝낼 필요" 는 오히려 높인다. 둘은 다른 질문이라
    프로젝트는 스킬 순위와 무관하게 자기 자격으로 후보가 된다.
    """
    need_by_skill = {
        entry["skill"].id: entry["priority_score"] for entry in entries
    }

    running = []

    for project in db.query(models.Project).all():
        if not project.career_related or project.status == "completed":
            continue

        if (project.progress_percent or 0) >= 100:
            continue

        deadline = _parse_target_date(project.target_date)
        days_left = (deadline - today).days if deadline else None

        running.append({
            "project": project,
            "days_left": days_left,
            "progress": project.progress_percent or 0,
            "need": max(
                (need_by_skill.get(skill.id, 0) for skill in project.skills),
                default=0,
            ),
        })

    # 마감이 가까운 것 → 거의 끝난 것 → 중요한 스킬을 증명하는 것.
    # 거의 끝난 것을 먼저 두는 이유는, 20% 짜리를 여러 개 벌여두면
    # 증거가 하나도 안 남기 때문이다.
    running.sort(
        key=lambda item: (
            item["days_left"] if item["days_left"] is not None else 9999,
            -item["progress"],
            -item["need"],
        )
    )

    candidates = []

    for item in running[:MAX_PROJECT_CANDIDATES]:
        project = item["project"]
        progress = item["progress"]

        if item["days_left"] is not None and item["days_left"] <= 7:
            reason = (
                f"마감까지 {item['days_left']}일 · 진행률 {progress}%."
            )
        elif progress >= 70:
            reason = (
                f"진행률 {progress}% — 조금만 더 하면 증거가 됩니다."
            )
        else:
            reason = (
                f"진행률 {progress}% 입니다. 만든 것이 곧 증거가 됩니다."
            )

        candidates.append({
            "task_type": "project",
            "title": project.name,
            "minutes": project.daily_minutes or 45,
            "reason": reason,
            "project_id": project.id,
            "days_left": item["days_left"],
            "urgent": item["days_left"] is not None
            and item["days_left"] <= DEADLINE_URGENT_DAYS,
        })

    return candidates


# 후보가 무엇을 가리키는지. 같은 것을 두 번 올리지 않으려고 쓴다.
LINK_FIELDS = (
    "routine_id",
    "project_id",
    "learning_step_id",
    "learning_resource_id",
    "application_id",
    "opportunity_id",
)


def _identity(candidate: dict):
    """이 후보가 가리키는 대상.

    가리키는 것이 없으면 제목으로 본다.
    """
    for field in LINK_FIELDS:
        value = candidate.get(field)

        if value is not None:
            return (field, value)

    return ("title", candidate.get("title"))


def _dedupe(candidates: list[dict]) -> list[dict]:
    """같은 것을 두 번 올리지 않는다.

    이월과 신규 후보가 같은 대상을 가리킬 수 있다. 실제로 났다 —
    어제 못 끝낸 프로젝트가 이월로 한 번, "진행 중이니 오늘도
    하라" 는 신규 후보로 또 한 번 올라와 하루 세 칸 중 두 칸을
    같은 일이 차지했다.

    먼저 온 것을 남긴다. 앞쪽이 더 중요한 순서다(마감 → 이월 → …).
    """
    seen = set()
    kept = []

    for candidate in candidates:
        key = _identity(candidate)

        if key in seen:
            continue

        seen.add(key)
        kept.append(candidate)

    return kept


def build_candidates(db, today: date) -> list[dict]:
    """오늘 후보가 될 수 있는 일들. 아직 시간 배분 전이다.

    순서가 중요도 순이다.
      1. 마감 임박            — 놓치면 되돌릴 수 없다 (지원 · 기회, 3일 안)
      2. 이월                 — 어제 못 한 것을 그냥 버리지 않는다
      3. 마감 있는 학습 · 프로젝트 — 14일 안, 가까운 순
      4. 학습                 — 우선순위 1위 스킬의 다음 단계
      5. 나머지 프로젝트       — 진행 중인 것. 스킬 순위와 무관하게 올라온다

    루틴은 여기 없다 — generate_plan 이 시간부터 떼어 둔다.
    커리어 증거가 아닌 프로젝트(취미)는 _project_candidates 가 이미 뺀다.
    """
    candidates = []

    entries = priority_service.build_skill_priorities(db)
    projects = _project_candidates(db, entries, today)

    dated_projects = [
        item
        for item in projects
        if item["days_left"] is not None and item["days_left"] <= DEADLINE_HORIZON_DAYS
    ]
    dated = _due_learning_candidates(db, today) + dated_projects
    dated.sort(key=lambda item: item["days_left"])

    # 3일 안에 마감인 학습 · 프로젝트는 이월보다 앞이다. 실제로 났다 —
    # 토요일 발표(D-3)가 어제 못 한 자료 두 개에 칸을 뺏겨 계획에서 빠졌다.
    # 이월은 내일 해도 되지만 발표일은 옮길 수 없다.
    candidates.extend(_deadline_candidates(db, today))
    candidates.extend(item for item in dated if item["urgent"])
    candidates.extend(_carry_over_candidates(db, today))
    candidates.extend(item for item in dated if not item["urgent"])

    if entries:
        learning = _learning_candidate(db, entries[0])
        if learning:
            candidates.append(learning)

    # 프로젝트는 스킬 순위를 타지 않는다. 자기 자격으로 온다.
    candidates.extend(item for item in projects if item not in dated_projects)

    return _dedupe(candidates)


# --------------------------------
# 시간 배분
# --------------------------------

def allocate(candidates: list[dict], available_minutes: int, intensity: dict):
    """가용 시간과 강도에 맞게 자른다.

    강도가 정하는 것:
      max_tasks   몇 개까지 둘 것인가
      max_block   한 덩어리를 얼마나 길게 허용할 것인가
      min_block   남은 시간이 이보다 작으면 더 넣지 않는다 (자투리 방지)

    min_block 은 일의 길이를 거르는 기준이 아니다.
    짧은 일은 짧은 대로 넣는다.
    """
    chosen = []
    remaining = max(0, available_minutes)

    for candidate in candidates:
        if len(chosen) >= intensity["max_tasks"]:
            break

        if remaining < intensity["min_block"]:
            break

        wanted = candidate["minutes"] or intensity["min_block"]

        # min_block 은 "남은 자투리 시간은 쓰지 않는다" 는 뜻이다.
        # 일 자체가 짧다고 버리는 규칙이 아니다.
        # 40분짜리 최우선 학습을 45분에 못 미친다고 빼면 계획이 나빠진다.
        minutes = min(wanted, intensity["max_block"], remaining)

        item = dict(candidate)
        item["minutes"] = minutes
        chosen.append(item)

        remaining -= minutes

    return chosen, remaining


# --------------------------------
# 저장
# --------------------------------

def generate_plan(
    db,
    available_minutes: int = DEFAULT_AVAILABLE_MINUTES,
    intensity_name: str = DEFAULT_INTENSITY,
    today: date | None = None,
):
    """오늘 계획을 만들어 저장한다.

    이미 끝낸 일은 건드리지 않는다. 아직 안 한 것만 새로 짠다.
    """
    today = today or date.today()
    intensity = get_intensity(intensity_name)

    # 완료/건너뜀은 기록으로 남긴다. planned 만 다시 짠다.
    (
        db.query(models.DailyPlanTask)
        .filter(
            models.DailyPlanTask.plan_date == today,
            models.DailyPlanTask.status == "planned",
        )
        .delete(synchronize_session=False)
    )
    db.flush()

    done_minutes = sum(
        task.minutes
        for task in _stored_tasks(db, today)
        if task.status == "done"
    )

    stored = _stored_tasks(db, today)
    budget = max(0, available_minutes - done_minutes)

    # 루틴은 시간을 먼저 떼어 둔다. 강도의 칸 수(max_tasks)는 쓰지 않는다 —
    # 코테 30분이 하루 세 칸 중 한 칸을 차지하면 학습이 밀려난다.
    # 오늘 이미 끝냈거나 넘긴 루틴은 다시 넣지 않는다.
    handled = {task.routine_id for task in stored if task.routine_id is not None}
    routines = []

    for item in routine_service.plan_candidates(db, today, exclude=handled):
        if item["minutes"] > budget:
            continue
        routines.append(item)
        budget -= item["minutes"]

    # 루틴이 이미 여는 학습 단계는 후보에서 뺀다. 같은 일을 두 번 올리지 않는다.
    routine_steps = {item["learning_step_id"] for item in routines if item["learning_step_id"]}
    candidates = [
        item
        for item in build_candidates(db, today)
        if item.get("learning_step_id") not in routine_steps
    ]

    chosen, remaining = allocate(candidates, budget, intensity)

    # 급한 마감 → 루틴 → 나머지. 루틴은 매일 같은 자리에 있어야 찾기 쉽다.
    chosen = (
        [item for item in chosen if item.get("urgent")]
        + routines
        + [item for item in chosen if not item.get("urgent")]
    )

    start_position = len(stored)

    for index, item in enumerate(chosen):
        db.add(models.DailyPlanTask(
            plan_date=today,
            position=start_position + index,
            task_type=item["task_type"],
            title=item["title"],
            minutes=item["minutes"],
            reason=item.get("reason", ""),
            status="planned",
            carried_from=item.get("carried_from"),
            plan_available_minutes=available_minutes,
            plan_intensity=intensity_name,
            learning_step_id=item.get("learning_step_id"),
            project_id=item.get("project_id"),
            learning_resource_id=item.get("learning_resource_id"),
            application_id=item.get("application_id"),
            opportunity_id=item.get("opportunity_id"),
            routine_id=item.get("routine_id"),
        ))

    db.commit()

    return build_plan(db, today, available_minutes, intensity_name)


def _stored_tasks(db, today: date):
    return (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.plan_date == today)
        .order_by(models.DailyPlanTask.position)
        .all()
    )


# 화면에 보일 영역 이름. 원시값(learning_step)을 보이지 않는다.
AREA_LABELS = {
    "learning_step": "학습",
    "resource": "자료",
    "project": "프로젝트",
    "application": "지원",
    "opportunity": "기회",
    "routine": "루틴",
}


def preview_completion(task) -> str:
    """완료를 누르면 무엇이 바뀌는지 — 누르기 전에 말한다.

    실제로 바꾸는 것은 complete_task 다. 여기는 같은 규칙으로 미리 센다.
    자동으로 바뀌지 않는 것은 바뀌지 않는다고 쓴다. 체크 한 번에
    프로젝트 진행률이 오를 거라고 기대하게 두면 거짓 진행도가 된다.
    """
    if task.routine is not None:
        target = routine_service.target_text(task.routine)
        return (
            f"오늘 {target} 한 것으로 기록합니다. 실제 개수는 완료할 때 적을 수 있어요."
            if target
            else "오늘 한 것으로 기록합니다."
        )

    step = task.learning_step

    if step is not None:
        if step.status == learning_service.COMPLETED:
            return "이 학습 단계는 이미 끝났습니다. 오늘 한 기록만 남습니다."

        unchecked = checklist_service.remaining(step)
        if unchecked:
            return (
                f"오늘 한 기록이 남습니다. 체크 안 한 항목이 {unchecked}개라 "
                "단계는 끝나지 않고 진행 중으로 둡니다."
            )

        path = step.learning_path
        summary = learning_service.summarize_steps(path)
        total = summary["total_steps"]
        after = (
            round((summary["completed_steps"] + 1) / total * 100) if total else 0
        )

        return (
            f"학습 단계가 완료로 바뀌고 '{path.title}' 진행률이 "
            f"{summary['progress_percent']}% → {after}% 가 됩니다."
        )

    if task.learning_resource_id is not None:
        return "오늘 한 기록이 남습니다. 자료의 챕터 체크는 내 자료 화면에서 직접 해 주세요."

    if task.project_id is not None:
        return "오늘 한 기록이 남습니다. 프로젝트 진행률은 프로젝트 화면에서 직접 올려 주세요."

    if task.application_id is not None:
        return "오늘 한 기록이 남습니다. 자기소개서와 상태는 지원서 화면에서 바뀝니다."

    if task.opportunity_id is not None:
        return "오늘 한 기록이 남습니다. 지원하기로 했다면 기회 화면에서 지원서를 만드세요."

    return "오늘 한 기록이 남습니다."


def serialize_task(task) -> dict:
    return {
        "id": task.id,
        "position": task.position,
        "task_type": task.task_type,
        "title": task.title,
        "minutes": task.minutes,
        "reason": task.reason,
        "status": task.status,
        "completed_at": task.completed_at,
        "carried_from": task.carried_from,
        "learning_step_id": task.learning_step_id,
        "project_id": task.project_id,
        "learning_resource_id": task.learning_resource_id,
        "application_id": task.application_id,
        "opportunity_id": task.opportunity_id,
        "routine_id": task.routine_id,
        "routine": (
            routine_service.task_summary(task.routine)
            if task.routine is not None
            else None
        ),
        "area": AREA_LABELS.get(task.task_type, "할 일"),
        "on_complete": preview_completion(task),
        # 학습 단계는 하루에 안 끝난다. 오늘 실제로 할 줄을 같이 보인다.
        "checklist": (
            checklist_service.summary(task.learning_step)
            if task.learning_step is not None
            else None
        ),
    }


def build_plan(
    db,
    today: date | None = None,
    available_minutes: int = DEFAULT_AVAILABLE_MINUTES,
    intensity_name: str = DEFAULT_INTENSITY,
) -> dict:
    """저장된 오늘 계획을 읽어서 돌려준다."""
    today = today or date.today()

    tasks = _stored_tasks(db, today)

    # 저장된 계획이 있으면 그때 쓴 설정을 따른다.
    # 조회 파라미터를 그대로 쓰면 실제와 다른 "남은 시간" 이 나온다.
    for task in tasks:
        if task.plan_available_minutes is not None:
            available_minutes = task.plan_available_minutes
            intensity_name = task.plan_intensity or intensity_name
            break

    intensity = get_intensity(intensity_name)

    planned_minutes = sum(t.minutes for t in tasks if t.status != "skipped")
    done_minutes = sum(t.minutes for t in tasks if t.status == "done")
    done_count = sum(1 for t in tasks if t.status == "done")

    return {
        "date": today,
        "available_minutes": available_minutes,
        "intensity": intensity_name,
        "intensity_label": intensity["label"],
        "planned_minutes": planned_minutes,
        "done_minutes": done_minutes,
        "remaining_minutes": max(0, available_minutes - planned_minutes),
        "total_tasks": len(tasks),
        "done_tasks": done_count,
        "carried_over": sum(1 for t in tasks if t.carried_from is not None),
        "deadlines": collect_deadlines(db, today),
        "tasks": [serialize_task(t) for t in tasks],
        # 사흘 넘게 밀린 것. 계획에는 안 올라가고 여기서 물어본다.
        "stale": stale_carry_overs(db, today),
    }


def release_plan_tasks(db, column, value) -> dict:
    """지워진 것을 가리키는 계획 항목을 정리한다.

    아직 안 한 것은 지운다. 남겨두면 없는 공고에 지원 준비를
    하라고 말하게 된다 — 지어낸 할 일이다.

    이미 한 것은 남기고 연결만 끊는다. 그날 무엇을 했는지는
    가리키던 대상이 사라졌다고 없어져도 되는 기록이 아니다.
    제목은 만들 때 함께 저장해두므로 연결이 끊겨도 읽을 수 있다.

    호출하는 쪽에서 commit 한다 — 지우는 것과 같은 트랜잭션이어야
    한다.
    """
    tasks = (
        db.query(models.DailyPlanTask)
        .filter(column == value)
        .all()
    )

    removed = 0
    kept = 0

    for task in tasks:
        if task.status == "done":
            setattr(task, column.key, None)
            kept += 1
        else:
            db.delete(task)
            removed += 1

    return {"removed": removed, "kept": kept}


def complete_task(db, task, count: int | None = None):
    """완료 처리. 실제 대상까지 함께 갱신한다.

    체크만 하고 원래 데이터가 그대로면 진행도가 거짓이 된다.

    - 루틴: 그날 기록을 남긴다 (count 를 안 주면 목표만큼). 연결된 학습 단계는
      끝내지 않는다 — 30분 했다고 한 단계가 끝나지 않는다.
    - 체크리스트가 남은 학습 단계: 하루 치를 했다고 단계를 끝내지 않는다.
    """
    task.status = "done"
    task.completed_at = datetime.now()

    effects = []

    if task.routine is not None:
        log = routine_service.record(db, task.routine, task.plan_date, count)
        effects.append(routine_service.describe_log(task.routine, log))

    elif (
        task.learning_step is not None
        and task.learning_step.status != "completed"
        and checklist_service.remaining(task.learning_step)
    ):
        step = task.learning_step
        unchecked = checklist_service.remaining(step)

        if step.status == learning_service.NOT_STARTED:
            step.status = learning_service.IN_PROGRESS
            db.flush()
            learning_service.recalculate_path_progress(
                db, step.learning_path, commit=False
            )

        effects.append(f"체크 안 한 항목 {unchecked}개가 남아 단계는 진행 중으로 둡니다")

    elif task.learning_step is not None and task.learning_step.status != "completed":
        step = task.learning_step
        step.status = "completed"
        step.progress_percent = 100
        step.completed_at = datetime.now()

        db.flush()

        learning_service.recalculate_path_progress(
            db, step.learning_path, commit=False
        )

        effects.append(f"학습 단계 완료 — {step.title}")

    db.commit()
    db.refresh(task)

    return {"task": serialize_task(task), "effects": effects}
