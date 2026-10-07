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

from sqlalchemy.orm import object_session

from .. import models
from . import checklist as checklist_service
from . import learning as learning_service
from . import routine as routine_service
from . import priority as priority_service
from . import market as market_service


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

# 기한 없이 빼둔 줄. planned / done / skipped 와 나란한 네 번째 상태다.
# 이월도 안 되고 계획을 다시 짜도 안 지워진다 — 둘 다 `planned` 만 보기 때문이다.
PARKED = "parked"

# 공고 · 지원은 "시간을 쓰는 일" 이 아니라 "정할 일" 이다.
#
# 15분짜리 "지원할지 정하기" 가 예산과 max_tasks 자리를 먹으면, 공고가 두세 건 들어온
# 날은 공부가 통째로 밀린다 (실제로 났다 — 세 자리 중 둘을 공고가 차지했다).
# 그래서 예산에서 빼고 자리도 세지 않는다. 목록에는 그대로 둔다 — 마감은 놓치면 끝이라
# 보이기는 해야 한다.
BUDGET_EXEMPT_TYPES = ("application", "opportunity")

# 아직 언제 할지 모르는 기획안. 프로젝트 목록에는 있지만 오늘 계획에는 안 올라온다.
PROJECT_IDEA = "idea"

# 오늘 할 일을 묶는 갈래. 원시값(task_type)만으로는 "학교 수업" 과 "따로 공부" 를
# 못 가른다 — 둘 다 learning_step 이다. 학습 경로의 kind 를 같이 봐야 갈라진다.
#
#   course   학교 일과 — 요일이 정해져 있고 앞 주차를 알아야 다음이 된다
#   study    따로 공부 — 스터디 · 책 · 심화. 마감 가까운 것부터
#   project  프로젝트
#   deciding 공고 · 지원 — 시간을 쓰는 일이 아니라 정할 일 (예산 밖)
#   other    그 밖
LANE_COURSE = "course"
LANE_STUDY = "study"
LANE_PROJECT = "project"
LANE_DECIDING = "deciding"
LANE_OTHER = "other"

LANE_LABELS = {
    LANE_COURSE: "학교 일과",
    LANE_STUDY: "따로 공부",
    LANE_PROJECT: "프로젝트",
    LANE_DECIDING: "공고 · 지원",
    LANE_OTHER: "그 밖",
}


def lane_of_task(task) -> str:
    """이 줄이 어느 갈래인가."""
    if task.task_type in BUDGET_EXEMPT_TYPES:
        return LANE_DECIDING

    if task.task_type == "project":
        return LANE_PROJECT

    step = getattr(task, "learning_step", None)
    path = getattr(step, "learning_path", None) if step is not None else None

    if path is not None:
        return LANE_COURSE if path.kind == "course" else LANE_STUDY

    if task.task_type in ("learning_step", "resource"):
        return LANE_STUDY

    return LANE_OTHER


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

    # **마감일 유무와 상관없이** 지원서가 있는 공고는 전부 덮는다.
    #
    # 전에는 `deadline IS NOT NULL` 인 지원서만 봤다. 지원서에 마감일을
    # 안 적으면 그 공고가 "아직 지원서를 만들지 않았습니다" 로 매일 되살아난다.
    # 실제로 났다 — SK인텔릭스에 지원한 날 오후에도 오늘 계획에 "지원할지
    # 정하기" 가 그대로 있었다. 마감일은 **후보를 고를 때** 필요한 것이지,
    # "이미 정했는가" 를 판단할 때 필요한 것이 아니다.
    for application in db.query(models.Application).all():
        if application.opportunity_id is not None:
            covered.add(application.opportunity_id)

    for application in db.query(models.Application).filter(
        models.Application.deadline.isnot(None)
    ):
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

    # 학교 일 — 캡스톤 목표일, 논문 스터디 발표 주차. 공고보다 이쪽이 더 못 미룬다.
    # 전에는 계획 안에만 들어오고 띠에는 안 떠서, "오늘 뭐가 급한가" 에 학교가 빠져 있었다.
    projects = (
        db.query(models.Project)
        .filter(models.Project.target_date.isnot(None), models.Project.target_date != "")
        .filter(models.Project.status != "completed")
        .all()
    )

    for project in projects:
        days = _days_left(_parse_target_date(project.target_date), today)

        if days is None or days < 0 or days > DEADLINE_HORIZON_DAYS:
            continue

        items.append({
            "kind": "project",
            "id": project.id,
            "title": project.name,
            "status": project.status,
            "days_left": days,
        })

    steps = (
        db.query(models.LearningStep)
        .filter(models.LearningStep.due_date.isnot(None))
        .filter(models.LearningStep.status != learning_service.COMPLETED)
        .all()
    )

    for step in steps:
        days = _days_left(step.due_date, today)

        if days is None or days < 0 or days > DEADLINE_HORIZON_DAYS:
            continue

        items.append({
            "kind": "learning_step",
            "id": step.id,
            "title": step.title,
            "status": step.status,
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

        # 마감이 지난 공고 · 이미 낸 지원 · 끝낸 단계는 다시 안 올린다.
        if _settled_reason(task, today) is not None:
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
            # 이게 빠져 있었다. 그러면 _task_key 가 제목으로 떨어져서, 같은 공고의
            # 마감 후보(opportunity_id 있음)와 이월 후보(없음)가 다른 일로 보였다 —
            # 화면에 "기회" 와 "기회 · 이월" 두 줄이 나왔다.
            "opportunity_id": task.opportunity_id,
            "urgent": False,
        })

    return candidates


# 저절로 치우는 이유. 사람이 판단할 게 없는 것들만 넣는다 —
# "마감이 지났다" 는 사실이고, "이거 안 할 건가요?" 는 질문이다.
SETTLED_DEADLINE = "마감이 지났습니다"
SETTLED_DROPPED = "안 가기로 정한 공고입니다"
SETTLED_APPLIED = "이미 지원서를 만들었습니다"
SETTLED_DONE = "이미 끝낸 것입니다"
SETTLED_GONE = "가리키던 것이 지워졌습니다"


def _settled_reason(task, today: date) -> str | None:
    """이 할 일은 더 물어볼 게 없는가. 없으면 그 이유, 있으면 None.

    **사실만 본다.** 마감이 지난 공고에 "지원할지 정하기" 를 물어볼 수는
    없다. 이미 지원서를 만들었으면 정하기는 끝났다. 끝낸 단계가 다시
    올라올 이유도 없다.

    이게 없어서 "이건 안 할 건가요?" 칸이 열한 줄이 됐다. 그중 여럿은
    답이 이미 정해진 것이었고, 진짜 물어볼 것들이 거기 묻혔다.
    """
    if task.opportunity_id is not None:
        opportunity = task.opportunity

        if opportunity is None:
            return SETTLED_GONE

        if opportunity.applications:
            return SETTLED_APPLIED

        if opportunity.status in market_service.DEMAND_OFF_STATUS:
            return SETTLED_DROPPED

        deadline = opportunity.deadline
        if isinstance(deadline, datetime):
            deadline = deadline.date()
        if deadline is not None and deadline < today:
            return SETTLED_DEADLINE

    if task.application_id is not None and task.application is None:
        return SETTLED_GONE

    if task.learning_step_id is not None:
        step = task.learning_step
        if step is None:
            return SETTLED_GONE
        if step.status == "completed":
            return SETTLED_DONE

    if task.project_id is not None:
        project = task.project
        if project is None:
            return SETTLED_GONE
        if project.status == "completed":
            return SETTLED_DONE

    if task.learning_resource_id is not None and task.learning_resource is None:
        return SETTLED_GONE

    return None


def settle_for_opportunity(db, opportunity_id: int, today: date | None = None) -> list[dict]:
    """이 공고로 지원서를 만들었다 — 오늘 계획의 "지원할지 정하기" 를 끝낸다.

    **그 자리에서 해야 한다.** 다시 짤 때까지 기다리면 이미 지원한 공고가
    오늘 할 일로 남아 있다. 실제로 수현이 SK인텔릭스에 지원한 당일 오후에도
    "아직 지원서를 만들지 않았습니다" 가 그대로 떠 있었다.

    넘긴 것이 아니라 **끝낸 것**으로 표시한다 — 지원할지 정하는 일은
    실제로 끝났기 때문이다.
    """
    today = today or date.today()

    rows = (
        db.query(models.DailyPlanTask)
        .filter(
            models.DailyPlanTask.opportunity_id == opportunity_id,
            models.DailyPlanTask.status.in_(("planned", PARKED)),
        )
        .all()
    )

    settled = []

    for task in rows:
        task.status = "done"
        task.completed_at = datetime.now()
        settled.append({"task_id": task.id, "title": task.title})

    # 즐겨찾기도 내린다. 즐겨찾기는 "잊지 않게 여기 둬" 라는 뜻인데,
    # 지원서를 낸 뒤에는 잊을 일이 없다 — 지원서 목록에 있다.
    opportunity = db.get(models.Opportunity, opportunity_id)

    if opportunity is not None and opportunity.favorite:
        opportunity.favorite = False
        settled.append({"task_id": None, "title": f"{opportunity.title} 즐겨찾기"})

    if settled:
        db.commit()

    return settled


def clear_settled_tasks(db, today: date | None = None) -> list[dict]:
    """답이 이미 정해진 이월을 실제로 치운다. 치운 것을 돌려준다.

    **계획을 다시 짤 때만 부른다.** 읽기(build_plan)는 데이터를 바꾸지
    않는다는 규칙을 지킨다 — 대신 읽는 쪽은 `_settled_reason` 으로
    걸러서 보여주기만 한다.

    지우지 않고 `skipped` 로 둔다 — 자국이 남아야 "되돌리기" 가 되고,
    무엇이 왜 사라졌는지도 말할 수 있다. 조용히 없애지 않는다.
    """
    today = today or date.today()

    cleared = []

    for task in _leftover_tasks(db, today):
        reason = _settled_reason(task, today)

        if reason is None:
            continue

        task.status = "skipped"
        cleared.append({
            "task_id": task.id,
            "title": task.title,
            "reason": reason,
        })

    if cleared:
        db.commit()

    return cleared


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
        # 답이 이미 정해진 것은 묻지 않는다. 마감이 지난 공고에
        # "지원할지 정하기" 를 물어볼 수는 없다. 이것들이 섞여서
        # 칸이 열한 줄이 됐고, 진짜 물어볼 것들이 거기 묻혔다.
        and _settled_reason(task, today) is None
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

        # 프로젝트 · 학습 단계는 아래 dated 후보가 이미 할 일로 만든다.
        # 여기서 또 만들면 같은 일이 계획에 두 번 앉는다.
        if item["kind"] in ("project", "learning_step"):
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

    **루틴이 맡은 경로는 빼둔다.** 루틴이 이미 오늘 몫 한 단계를 떼어 두기
    때문이다. 실제로 났다 — 하루에 한 단계씩 짠 사흘짜리 시험 계획에서
    오늘 것은 루틴이, 내일 · 모레 것은 마감 학습이 각각 올려 하루 계획에
    사흘이 한꺼번에 들어왔다.
    """
    horizon = today + timedelta(days=DEADLINE_HORIZON_DAYS)
    found = []

    routine_paths = {
        path_id
        for (path_id,) in db.query(models.Routine.learning_path_id).filter(
            models.Routine.active.is_(True),
            models.Routine.learning_path_id.isnot(None),
        )
    }

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
        if step.learning_path_id in routine_paths:
            continue
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
        if path.id in routine_paths:
            continue
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
        # 학습용(수업 과제)도 오늘 할 일이다. 취미만 뺀다.
        if project.purpose == "hobby" or not project.career_related:
            continue

        if project.status == "completed":
            continue

        # 기획안(idea)은 계획에 올리지 않는다.
        #
        # "언제 할지 모르겠지만 하고 싶다" 를 적어두는 칸이다. 그걸 매일 할 일로 띄우면
        # 적어두는 것 자체가 부담이 되어 아무것도 안 적게 된다. 시작할 때 사람이
        # status 를 planned/in_progress 로 바꾼다.
        if project.status == PROJECT_IDEA:
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

    # 세우는 순간의 1위 스킬을 같이 남긴다. 나중에 1위가 바뀌면 화면이 "계획이 낡았다" 고 말한다.
    priorities = priority_service.build_skill_priorities(db)
    focus_skill = priorities[0]["skill"].name if priorities else None

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

    # 이미 저장된 중복을 접는다. 규칙을 고치기 전에 들어온 줄이 그대로 남아,
    # 같은 공고가 "넘김 · 넘김 · 할 일" 세 줄로 보였다.
    _fold_duplicates(db, today)

    # 답이 이미 정해진 이월을 치운다 (마감 지남 · 이미 지원함 · 끝낸 단계).
    # 읽기는 걸러서 보여주기만 하고, 실제로 표시하는 건 여기서 한다.
    cleared = clear_settled_tasks(db, today)

    done_minutes = sum(
        task.minutes
        for task in _stored_tasks(db, today)
        if task.status == "done"
    )

    stored = _stored_tasks(db, today)
    budget = max(0, available_minutes - done_minutes)

    # 루틴은 **계획에 넣지 않는다.** 대신 시간만 먼저 뗀다.
    #
    # 매일 하는 일은 "오늘 무엇을 할지" 의 판단 대상이 아니다. 코테는 평일마다 하는 것이지
    # 오늘 고른 것이 아니다. 계획 목록에 섞이면 매일 같은 줄이 자리를 차지하고,
    # 정작 오늘 정해야 할 일이 접힌 자리로 밀린다. 화면 맨 위 고정 칸에 따로 둔다.
    #
    # 시간은 그대로 뗀다 — 코테 30분은 실제로 30분이다. 떼지 않으면 계획이 하루를 넘긴다.
    handled = {task.routine_id for task in stored if task.routine_id is not None}
    routine_steps = set()

    for item in routine_service.plan_candidates(db, today, exclude=handled):
        if item["minutes"] > budget:
            continue
        budget -= item["minutes"]
        if item.get("learning_step_id"):
            routine_steps.add(item["learning_step_id"])

    # 루틴이 여는 학습 단계는 후보에서 뺀다. 같은 일을 두 번 올리지 않는다.
    # 오늘 이미 판에 있는 것(끝낸 것 · 넘긴 것)도 뺀다 — 넘길 때마다 같은 공고가
    # 새로 들어와 "지원할지 정하기" 가 세 줄이 됐다.
    # 미뤄둔 줄과 같은 대상도 뺀다. 빼둔 것이 다음 날 새 줄로 되살아나면
    # "기한 없이 빼둔다" 가 하루짜리 미루기가 된다.
    parked_keys = {_task_key(task) for task in parked_tasks(db)}

    candidates = [
        item
        for item in build_candidates(db, today)
        if item.get("learning_step_id") not in routine_steps
        and _task_key(item) not in {_task_key(task) for task in stored}
        and _task_key(item) not in parked_keys
    ]

    # 공고 · 지원은 예산과 자리를 먹지 않는다. 따로 떼어 뒤에 붙인다.
    #
    # allocate 를 거치지 않으므로 max_tasks 가 잘라주던 것이 없다. 같은 대상이
    # 마감 후보와 이월 후보로 두 번 들어올 수 있어 여기서 한 번만 남긴다.
    # (앞쪽이 마감 후보다 — build_candidates 가 마감을 먼저 넣는다.)
    deciding, seen = [], set()
    working = []
    for item in candidates:
        if item["task_type"] not in BUDGET_EXEMPT_TYPES:
            working.append(item)
            continue
        key = _task_key(item)
        if key in seen:
            continue
        seen.add(key)
        deciding.append(item)

    chosen, remaining = allocate(working, budget, intensity)
    chosen = chosen + deciding

    chosen = (
        [item for item in chosen if item.get("urgent")]
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
            plan_focus_skill=focus_skill,
            learning_step_id=item.get("learning_step_id"),
            project_id=item.get("project_id"),
            learning_resource_id=item.get("learning_resource_id"),
            application_id=item.get("application_id"),
            opportunity_id=item.get("opportunity_id"),
            routine_id=item.get("routine_id"),
        ))

    db.commit()

    plan = build_plan(db, today, available_minutes, intensity_name)

    # 저절로 치운 것. 조용히 없애지 않고 무엇을 왜 치웠는지 말해 준다.
    plan["cleared"] = cleared

    return plan


# 한 대상에 한 줄만 남길 때의 우선순위. 기록이 있는 쪽을 남긴다.
_KEEP_ORDER = {"done": 0, "planned": 1, "skipped": 2}


def _fold_duplicates(db, today: date) -> int:
    """같은 대상을 가리키는 오늘 줄이 여럿이면 하나만 남긴다.

    남기는 것은 끝낸 것 > 할 일 > 넘긴 것 순. 끝낸 기록은 지우지 않는다.
    """
    seen = {}
    removed = 0

    for task in _stored_tasks(db, today):
        key = _task_key(task)
        kept = seen.get(key)

        if kept is None:
            seen[key] = task
            continue

        loser = max((kept, task), key=lambda row: (_KEEP_ORDER.get(row.status, 3), row.position))
        winner = kept if loser is task else task

        seen[key] = winner
        db.delete(loser)
        removed += 1

    if removed:
        db.flush()

    return removed


def _task_key(task):
    """오늘 판에서 같은 일인지 가리는 열쇠.

    dict(후보)와 DailyPlanTask 를 같은 방법으로 읽는다. 가리키는 대상이 있으면 그것으로,
    없으면 제목으로 본다 — 제목만 있는 후보도 두 번 올라오면 안 된다.
    """
    def value(name):
        return task.get(name) if isinstance(task, dict) else getattr(task, name, None)

    for name in (
        "opportunity_id", "application_id", "learning_step_id",
        "project_id", "learning_resource_id", "routine_id",
    ):
        found = value(name)
        if found is not None:
            return (name, found)

    return ("title", value("title"))


def _visible_tasks(tasks: list) -> list:
    """화면에 보일 줄. 같은 대상은 하나만 — 끝낸 것 > 할 일 > 넘긴 것 순."""
    best = {}

    for task in tasks:
        key = _task_key(task)
        kept = best.get(key)

        if kept is None or (_KEEP_ORDER.get(task.status, 3), task.position) < (
            _KEEP_ORDER.get(kept.status, 3), kept.position
        ):
            best[key] = task

    chosen = set(id(task) for task in best.values())

    return [task for task in tasks if id(task) in chosen]


def _stored_tasks(db, today: date):
    return (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.plan_date == today)
        .order_by(models.DailyPlanTask.position)
        .all()
    )


def parked_tasks(db):
    """기한 없이 빼둔 것 — "언젠가 할 일".

    오늘 계획에서 밀어냈지만 버리지는 않은 줄이다. 날짜에 묶이지 않는다:
    plan_date 와 무관하게 모으므로 다음 날에도 그대로 보인다.

    이월(_leftover_tasks)과 다시 짜기(generate_plan)는 `planned` 만 보므로
    여기 있는 줄은 저절로 빠진다 — 오늘 계획을 밀어내지 않는다.
    """
    return (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.status == PARKED)
        .order_by(
            models.DailyPlanTask.plan_date,
            models.DailyPlanTask.position,
        )
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
        # 화면이 갈래로 묶는다 — 무조건 하는 일(루틴)은 이미 따로 있고, 나머지를 넷으로 나눈다.
        "lane": lane_of_task(task),
        "lane_label": LANE_LABELS.get(lane_of_task(task), "그 밖"),
        "on_complete": preview_completion(task),
        # 자료(책 · 강의)는 통째로 "시작" 할 수 없다. 오늘 읽을 데를 같이 준다.
        "resource": (
            _resource_summary(task.learning_resource)
            if task.learning_resource is not None
            else None
        ),
        # 학습 단계는 하루에 안 끝난다. 오늘 실제로 할 줄을 같이 보인다.
        "checklist": (
            # 오늘 이 할 일에 준 시간만큼만 자른다 — 주차 하나가 9시간이면
            # 그걸 통째로 "오늘 할 일" 이라고 내밀 수 없다.
            #
            # 자를 때 **보정 계수**를 쓴다. 지금까지 계획보다 1.4배 걸렸다면
            # 30분에 다섯 항목이 아니라 세 항목이 맞다. 기록이 적으면
            # 보정하지 않는다 (pace_factor 가 None 을 돌려준다).
            checklist_service.summary(
                task.learning_step, task.minutes,
                factor=_pace_factor_value(object_session(task)),
            )
            if task.learning_step is not None
            else None
        ),
    }


def _resource_summary(resource) -> dict:
    """이 자료로 오늘 **어디를** 할지.

    제목만 주면 "시작" 을 눌러도 열 데가 없어 내 자료 목록으로 떨어진다.
    실제로 그랬다 — 책에서 시작을 눌렀는데 아무것도 안 나왔다. 책 한 권은
    오늘 할 일이 될 수 없고, 1장 45분은 될 수 있다.

    조각(segment)이 없으면 next_segment 는 None 이다. 그때는 화면이
    "어디부터 읽을지 먼저 나누세요" 라고 말해야 한다 — 없는 범위를
    지어내지 않는다.
    """
    segments = sorted(resource.segments, key=lambda item: (item.position, item.id))

    upcoming = next(
        (item for item in segments if item.status != "completed"), None
    )

    return {
        "id": resource.id,
        "title": resource.title,
        "url": resource.url or "",
        "resource_type": resource.resource_type,
        "segment_total": len(segments),
        "segment_done": sum(1 for item in segments if item.status == "completed"),
        "next_segment": (
            {
                "id": upcoming.id,
                "label": upcoming.label,
                "minutes": upcoming.estimated_minutes,
                "start_ref": upcoming.start_ref,
                "end_ref": upcoming.end_ref,
                # 이미 적어 둔 게 있으면 그걸 보여준다 — 덮어쓰지 않게.
                "note": upcoming.note or "",
            }
            if upcoming is not None
            else None
        ),
        # 바로 앞 조각에 남긴 한 줄. 이어 읽을 때 "지난번에 뭐였더라" 가
        # 화면에 있어야 다시 열어보지 않는다.
        "last_note": next(
            (
                {"label": item.label, "note": item.note}
                for item in reversed(segments)
                if item.status == "completed" and (item.note or "").strip()
            ),
            None,
        ),
    }


# 보정에 쓸 최소 기록 수. 이보다 적으면 비율을 내지 않는다 —
# 두세 번으로 "1.4배 걸린다" 고 말할 수 없다.
PACE_MIN_SAMPLES = 5

# 비율의 상·하한. 한 번 크게 어긋난 기록이 전체를 끌고 가지 않게 한다.
PACE_FLOOR, PACE_CEIL = 0.5, 2.5


def _pace_factor_value(db) -> float | None:
    """보정 계수만.

    serialize_task 는 db 를 안 받는다 — 부르는 데가 여럿이라 시그니처를
    바꾸면 전부 고쳐야 한다. 대신 객체가 달린 세션을 쓴다. 세션이 없으면
    (떼어낸 객체) 보정하지 않는다.
    """
    if db is None:
        return None

    found = pace_factor(db)
    return found["factor"] if found else None


def pace_factor(db, lane: str | None = None) -> dict | None:
    """계획한 시간 대비 실제로 몇 배가 걸리는가.

    수현: "시간을 넣으면 그 학습 시간에 맞춰서 해줄 수 있잖아."

    앱이 "180분" 이라고 적어 둔 추정은 한 번도 검증된 적이 없다. 실제로
    적은 시간이 쌓이면 그 추정을 보정할 수 있다 — 오늘 몫을 자르는 것도,
    구간 속도도 전부 추정 위에 서 있기 때문이다.

    **기록이 적으면 비율을 내지 않는다.** 두세 번으로 "1.4배" 라고 말하면
    그 숫자가 다음 계획을 통째로 흔든다.
    """
    query = (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.actual_minutes.isnot(None))
        .filter(models.DailyPlanTask.minutes > 0)
    )

    rows = [task for task in query.all() if lane is None or lane_of_task(task) == lane]

    if len(rows) < PACE_MIN_SAMPLES:
        return None

    planned = sum(task.minutes for task in rows)
    actual = sum(task.actual_minutes for task in rows)

    if not planned:
        return None

    factor = max(PACE_FLOOR, min(PACE_CEIL, actual / planned))

    return {
        "samples": len(rows),
        "planned_minutes": planned,
        "actual_minutes": actual,
        "factor": round(factor, 2),
    }


def plan_outdated(db, tasks) -> dict | None:
    """계획을 세운 뒤 판단의 재료가 바뀌었는가.

    계획은 세운 순간의 판단으로 저장된다. 실제로 났다 — 계획을 세운 뒤 고용24 공고가
    들어와 기회가 4건에서 10건이 됐고, 1위가 Machine Learning 에서 PyTorch 로 바뀌었다.
    그런데 할 일의 이유는 "Machine Learning 이 1위 · 4건 중 4건" 을, 옆의 "왜 이 계획인가" 는
    "PyTorch · 10건 중 3건" 을 말했다. 계산은 둘 다 맞았고, 낡았다고 말하지 않은 게 문제였다.

    다시 짜지는 않는다. 끝낸 일이 섞여 있고, 다시 세울지는 사람이 정한다.
    """
    planned = [task for task in tasks if task.status == "planned"]
    if not planned:
        return None

    made_at = min(task.created_at for task in planned)
    before = next((task.plan_focus_skill for task in planned if task.plan_focus_skill), None)

    priorities = priority_service.build_skill_priorities(db)
    now = priorities[0]["skill"].name if priorities else None

    new_opportunities = (
        db.query(models.Opportunity)
        .filter(models.Opportunity.collected_at > made_at)
        .count()
    )

    reasons = []
    if before and now and before != now:
        # 스킬 이름 뒤에 조사를 붙이지 않는다 — "Machine Learning 로" 처럼 틀린다.
        reasons.append(f"우선순위 1위가 바뀌었어요 ({before} → {now})")
    if new_opportunities:
        reasons.append(f"기회가 {new_opportunities}건 새로 들어왔어요")

    if not reasons:
        return None

    return {
        "reasons": reasons,
        "focus_before": before,
        "focus_now": now,
        "new_opportunities": new_opportunities,
    }


def today_routines(db, today: date) -> list[dict]:
    """오늘 할 차례인 루틴. 계획 항목이 아니라 고정 칸에 보일 것.

    코테는 평일마다 하는 것이지 오늘 고른 것이 아니다. 계획에 섞이면 매일 같은 줄이
    자리를 차지하고, 정작 오늘 정해야 할 일이 접힌 자리로 밀린다.
    """
    rows = (
        db.query(models.Routine)
        .filter(models.Routine.active.is_(True))
        .order_by(models.Routine.id)
        .all()
    )

    pinned = []

    for routine in rows:
        if not routine_service.is_due(routine, today):
            continue

        log = next((row for row in routine.logs if row.log_date == today), None)
        step = routine_service.next_step(routine.learning_path)

        pinned.append({
            "id": routine.id,
            "title": routine.title,
            "minutes": routine.minutes,
            "target_count": routine.target_count,
            "unit_label": routine.unit_label,
            "target_text": routine_service.target_text(routine),
            "link_url": routine.link_url,
            "note": routine.note,
            "learning_path": (
                {"id": routine.learning_path.id, "title": routine.learning_path.title}
                if routine.learning_path is not None
                else None
            ),
            "next_step": {"id": step.id, "title": step.title} if step else None,
            "done": log is not None,
            "count": log.count if log else None,
            # 그날 몰랐던 것. 개수를 적는 자리에서 같이 적는다 —
            # 끝낸 직후가 가장 잘 떠오르고, 나중에 다시 열 이유가 줄어든다.
            "learned": (log.learned or "") if log else "",
            "week": routine_service.week_summary(routine, today),
            "weekday_label": routine_service.weekday_label(routine),
        })

    return pinned


def build_plan(
    db,
    today: date | None = None,
    available_minutes: int = DEFAULT_AVAILABLE_MINUTES,
    intensity_name: str = DEFAULT_INTENSITY,
) -> dict:
    """저장된 오늘 계획을 읽어서 돌려준다."""
    today = today or date.today()

    # 같은 대상을 가리키는 줄이 여럿이면 화면에는 하나만 보인다.
    # 지우는 것은 계획을 다시 세울 때 한다 — 읽기가 데이터를 바꾸지 않는다.
    # 미뤄둔 줄은 오늘 목록에서 뺀다. 아래 "parked" 로 따로 나간다 —
    # 오늘 할 일에 섞이면 기한 없이 빼둔 뜻이 없어진다.
    tasks = [
        task
        for task in _visible_tasks(_stored_tasks(db, today))
        if task.status != PARKED
    ]

    # 저장된 계획이 있으면 그때 쓴 설정을 따른다.
    # 조회 파라미터를 그대로 쓰면 실제와 다른 "남은 시간" 이 나온다.
    for task in tasks:
        if task.plan_available_minutes is not None:
            available_minutes = task.plan_available_minutes
            intensity_name = task.plan_intensity or intensity_name
            break

    intensity = get_intensity(intensity_name)

    # 공고 · 지원은 시간을 쓰는 일로 세지 않는다. 세면 "남은 시간" 이 거짓이 된다.
    task_minutes = sum(
        t.minutes
        for t in tasks
        if t.status != "skipped" and t.task_type not in BUDGET_EXEMPT_TYPES
    )

    # 루틴은 계획 **목록** 에 없지만 예산은 실제로 먹는다 — generate_plan 이
    # 후보를 고르기 전에 루틴 시간부터 뗀다. 그런데 요약은 목록만 세고 있었다.
    # 그래서 "90분 중 50분" 이라고 말하면서 화면에는 코테 30분이 함께 떠 있었고,
    # 남았다는 40분을 믿고 하나 더 넣으면 하루가 넘쳤다. 같은 시간을 센다.
    #
    # 이미 계획 줄로 들어와 있는 루틴은 빼고 센다. 두 번 세면 반대로 모자란다.
    routines = today_routines(db, today)
    task_routine_ids = {t.routine_id for t in tasks if t.routine_id is not None}
    pinned = [r for r in routines if r["id"] not in task_routine_ids]

    routine_minutes = sum(r["minutes"] or 0 for r in pinned)

    planned_minutes = task_minutes + routine_minutes
    done_minutes = (
        sum(t.minutes for t in tasks if t.status == "done")
        + sum(r["minutes"] or 0 for r in pinned if r["done"])
    )
    done_count = sum(1 for t in tasks if t.status == "done")

    return {
        "date": today,
        "available_minutes": available_minutes,
        "intensity": intensity_name,
        "intensity_label": intensity["label"],
        "planned_minutes": planned_minutes,
        # 그중 루틴이 먹는 시간. 계획 목록에 없는 시간이 어디로 갔는지
        # 화면에서 말할 수 있어야 숫자를 믿을 수 있다.
        "routine_minutes": routine_minutes,
        "done_minutes": done_minutes,
        "remaining_minutes": max(0, available_minutes - planned_minutes),
        "total_tasks": len(tasks),
        "done_tasks": done_count,
        "carried_over": sum(1 for t in tasks if t.carried_from is not None),
        "deadlines": collect_deadlines(db, today),
        # 매일 하는 일 — 계획에 섞지 않고 화면 맨 위 고정 칸에 둔다.
        "routines": routines,
        "tasks": [serialize_task(t) for t in tasks],
        # 기한 없이 빼둔 것. 날짜에 묶이지 않아 오늘 것과 함께 매일 보인다.
        "parked": [serialize_task(t) for t in parked_tasks(db)],
        # 사흘 넘게 밀린 것. 계획에는 안 올라가고 여기서 물어본다.
        "stale": stale_carry_overs(db, today),
        # 계획한 시간 대비 실제로 몇 배가 걸렸나. 기록이 적으면 None.
        "pace_factor": pace_factor(db),

        # 계획을 세운 뒤 1위 스킬이 바뀌었거나 기회가 새로 들어왔으면 그 이유. 아니면 None.
        "outdated": plan_outdated(db, tasks),
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


# 직접 넣을 수 있는 것. 프로젝트 · 학습 단계 · 자료, 그리고 아무것도 안 가리키는 한 줄.
ADD_KINDS = ("project", "learning_step", "resource", "custom")


def add_task(db, kind: str, target_id=None, title: str = "", minutes: int = 30) -> dict:
    """오늘 계획에 사람이 직접 한 줄을 넣는다.

    앱이 고른 것만 할 수 있으면 "시간이 남아서 이걸 하고 싶다" 를 넣을 곳이 없다.
    계획은 제안이지 명령이 아니다. 대신 **무엇을 가리키는지**는 남긴다 —
    완료했을 때 진행률 · 증거가 같이 움직여야 하기 때문이다.
    """
    today = date.today()

    if kind not in ADD_KINDS:
        raise ValueError("넣을 수 있는 종류가 아니에요.")

    task_type = kind
    reason = "직접 넣었습니다."
    fields = {}

    if kind == "project":
        project = db.get(models.Project, target_id)
        if project is None:
            raise LookupError("그 프로젝트를 찾지 못했어요.")
        title = project.name
        fields["project_id"] = project.id
        reason = f"직접 넣었습니다. 진행률 {project.progress_percent or 0}%."

    elif kind == "learning_step":
        step = db.get(models.LearningStep, target_id)
        if step is None:
            raise LookupError("그 학습 단계를 찾지 못했어요.")
        path = step.learning_path
        title = f"{path.title} — {step.title}" if path else step.title
        fields["learning_step_id"] = step.id
        task_type = "learning_step"
        remaining = checklist_service.remaining(step)
        reason = "직접 넣었습니다." + (f" 체크 {remaining}개 남음." if remaining else "")

    elif kind == "resource":
        resource = db.get(models.LearningResource, target_id)
        if resource is None:
            raise LookupError("그 자료를 찾지 못했어요.")
        title = resource.title
        fields["learning_resource_id"] = resource.id
        task_type = "resource"

    else:
        title = (title or "").strip()
        if not title:
            raise ValueError("무엇을 할지 적어 주세요.")
        task_type = "custom"

    stored = _stored_tasks(db, today)

    # 이미 오늘 판에 있는 것은 두 번 넣지 않는다.
    candidate = {"title": title, **fields}
    if _task_key(candidate) in {_task_key(task) for task in stored}:
        return {"added": False, "reason": "이미 오늘 계획에 있어요.", "plan": build_plan(db, today)}

    db.add(models.DailyPlanTask(
        plan_date=today,
        position=len(stored),
        task_type=task_type,
        title=title[:200],
        minutes=minutes,
        reason=reason,
        status="planned",
        **fields,
    ))
    db.commit()

    return {"added": True, "reason": reason, "plan": build_plan(db, today)}


def reopen_task(db, task) -> dict:
    """완료 · 넘김을 되돌린다 — 잘못 눌렀으면 돌릴 수 있어야 한다.

    실제로 났다: 코테를 안 했는데 완료를 눌렀고, 되돌릴 방법이 없어 이번 주
    "했다" 에 거짓 하루가 남았다. 되돌릴 때는 완료가 바꾼 것도 같이 되돌린다.

    - 루틴: 그날 기록을 지운다.
    - 학습 단계: 이 완료가 단계를 끝냈으면(같은 순간에 끝났으면) 진행 중으로 되돌린다.
      그 전부터 끝나 있던 단계는 건드리지 않는다.
    """
    effects = []
    was_done = task.status == "done"
    finished_at = task.completed_at

    if was_done and task.routine is not None:
        if routine_service.unrecord(db, task.routine, task.plan_date):
            effects.append(f"{task.routine.title} 그날 기록을 지웠어요")

    step = task.learning_step
    if (
        was_done
        and step is not None
        and step.status == learning_service.COMPLETED
        and step.completed_at is not None
        and finished_at is not None
        and abs((step.completed_at - finished_at).total_seconds()) < 5
    ):
        step.status = learning_service.IN_PROGRESS
        step.completed_at = None
        step.progress_percent = 0
        db.flush()
        learning_service.recalculate_path_progress(db, step.learning_path, commit=False)
        effects.append(f"학습 단계 '{step.title}' 을(를) 진행 중으로 되돌렸어요")

    task.status = "planned"
    task.completed_at = None

    db.commit()
    db.refresh(task)

    return {"task": serialize_task(task), "effects": effects}


def complete_task(db, task, count: int | None = None, actual_minutes: int | None = None):
    """완료 처리. 실제 대상까지 함께 갱신한다.

    체크만 하고 원래 데이터가 그대로면 진행도가 거짓이 된다.

    - 루틴: 그날 기록을 남긴다 (count 를 안 주면 목표만큼). 연결된 학습 단계는
      끝내지 않는다 — 30분 했다고 한 단계가 끝나지 않는다.
    - 체크리스트가 남은 학습 단계: 하루 치를 했다고 단계를 끝내지 않는다.
    """
    task.status = "done"
    task.completed_at = datetime.now()

    # 실제로 걸린 시간. 안 적어도 끝낼 수 있다 — 적어야만 끝낼 수 있게
    # 하면 적기 싫어서 안 끝내게 되고, 그러면 기록이 더 나빠진다.
    if actual_minutes is not None:
        task.actual_minutes = actual_minutes

    effects = []

    if actual_minutes is not None and task.minutes:
        gap = actual_minutes - task.minutes
        if abs(gap) >= 10:
            effects.append(
                f"계획 {task.minutes}분 → 실제 {actual_minutes}분 "
                f"({'+' if gap > 0 else ''}{gap}분)"
            )

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
