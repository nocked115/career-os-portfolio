"""한눈에 보기 — 지금 상태를 이해하는 곳.

Today 는 행동하는 곳이고, 여기는 전체 상태를 요약하는 곳이다.
전에는 옛 대시보드 데이터(주간 계획 · 원시 우선순위 점수 · 공고 목록)를
영어 라벨로 늘어놓기만 했고 누를 곳이 없었다.

여기서 새로 판단하는 것은 없다. 각 서비스가 이미 내놓는 값을 모은다.
모든 숫자는 분모와 함께 준다 — "실행률 50%" 가 아니라 "4개 중 2개".
"""

from datetime import date, timedelta

from .. import models
from . import application_board
from . import certificates as certificate_service
from . import evidence as evidence_service
from . import profile as profile_service
from . import proof as proof_service
from . import today as today_service
from . import universe as universe_service


# 마감 임박으로 볼 기간. 지원서 보드의 "이번 주" 와 같다.
DEADLINE_WINDOW_DAYS = application_board.URGENT_DAYS


def _week(db, today: date) -> dict:
    """이번 주(월요일부터 오늘까지) 계획한 할 일 중 끝낸 비율.

    오늘 아직 안 한 것은 분모에 넣지 않는다 — 하루가 끝나지 않았다.
    """
    monday = today - timedelta(days=today.weekday())

    tasks = (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.plan_date >= monday)
        .filter(models.DailyPlanTask.plan_date <= today)
        .all()
    )

    done = sum(1 for task in tasks if task.status == "done")
    skipped = sum(1 for task in tasks if task.status == "skipped")
    missed = sum(
        1 for task in tasks if task.status == "planned" and task.plan_date < today
    )
    pending = sum(
        1 for task in tasks if task.status == "planned" and task.plan_date == today
    )
    decided = done + skipped + missed

    return {
        "from": monday,
        "to": today,
        "done": done,
        "skipped": skipped,
        "missed": missed,
        "pending_today": pending,
        "decided": decided,
        "rate": round(done / decided * 100) if decided else None,
    }


def _learning(db) -> dict:
    paths = db.query(models.LearningPath).all()
    steps = [step for path in paths for step in path.steps]

    active = next(
        (path for path in paths if any(s.status == "in_progress" for s in path.steps)),
        None,
    ) or next(
        (path for path in paths if any(s.status != "completed" for s in path.steps)),
        None,
    )

    next_step = None

    if active is not None:
        upcoming = sorted(
            (step for step in active.steps if step.status != "completed"),
            key=lambda step: (step.status != "in_progress", step.position, step.id),
        )[0]
        next_step = {"id": upcoming.id, "title": upcoming.title, "path": active.title}

    return {
        "paths": len(paths),
        "steps_done": sum(1 for step in steps if step.status == "completed"),
        "steps_total": len(steps),
        "next_step": next_step,
    }


def _projects(db) -> dict:
    projects = (
        db.query(models.Project)
        .filter(models.Project.career_related.is_(True))
        .all()
    )

    active = [project for project in projects if not proof_service.is_complete(project)]
    completed = [project for project in projects if proof_service.is_complete(project)]
    unproven = [
        project
        for project in completed
        if proof_service.existing_experience(db, project) is None
    ]

    return {
        "active": len(active),
        "completed": len(completed),
        "unproven": len(unproven),
        "unproven_names": [project.name for project in unproven][:3],
        "average_progress": (
            round(sum(project.progress_percent or 0 for project in active) / len(active))
            if active
            else None
        ),
    }


def _deadlines(db, today: date) -> dict:
    items = [
        item
        for item in today_service.collect_deadlines(db, today)
        if item["days_left"] <= DEADLINE_WINDOW_DAYS
    ]

    return {
        "within_days": DEADLINE_WINDOW_DAYS,
        "count": len(items),
        "nearest": items[0] if items else None,
    }


def build_overview(db, today: date | None = None) -> dict:
    today = today or date.today()

    me = profile_service.build_profile(db, today)
    plan = today_service.build_plan(db, today=today)
    upcoming = next((task for task in plan["tasks"] if task["status"] == "planned"), None)
    board = application_board.build_board(db, today)

    return {
        "date": today,
        "target": {
            "title": me.get("target_career"),
            "focus_skill": me.get("focus_skill"),
        },
        "readiness": universe_service._readiness(db),
        "next_action": (
            {
                "title": upcoming["title"],
                "minutes": upcoming["minutes"],
                "area": upcoming["area"],
                "reason": upcoming["reason"],
            }
            if upcoming
            else None
        ),
        "plan": {"total": plan["total_tasks"], "done": plan["done_tasks"]},
        "week": _week(db, today),
        "learning": _learning(db),
        "projects": _projects(db),
        "evidence": evidence_service.build_evidence(db),
        "applications": board["summary"],
        "deadlines": _deadlines(db, today),
        "certificates": certificate_service.build_list(db, today)["summary"],
    }
