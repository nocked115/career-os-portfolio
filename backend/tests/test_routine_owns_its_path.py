"""루틴이 맡은 경로는 계획이 따로 넣지 않는다.

하루에 한 단계씩 짠 사흘짜리 계획에서, 내일 · 모레 것까지 "마감 있는 학습" 으로 올라와
하루에 사흘이 다 들어왔다. 루틴은 계획이 아니라 고정 칸에 있고, 그 경로는 루틴이 맡는다.
"""

from datetime import date, timedelta

from app import models
from app.services import today as today_service


def _path_of_three_days(db, today):
    path = models.LearningPath(title="코테 사흘", status="in_progress")
    db.add(path)
    db.flush()

    for offset in range(3):
        db.add(models.LearningStep(
            learning_path_id=path.id,
            title=f"D-{3 - offset}",
            position=offset,
            estimated_minutes=60,
            due_date=today + timedelta(days=offset),
        ))
    db.commit()
    return path


def test_the_routine_owns_its_path_so_the_plan_leaves_it_alone(db_session):
    today = date.today()
    path = _path_of_three_days(db_session, today)

    db_session.add(models.Routine(
        title="코딩테스트", minutes=30, weekdays="0123456",
        learning_path_id=path.id, active=True,
    ))
    db_session.commit()

    plan = today_service.generate_plan(db_session, available_minutes=600, today=today)

    # 루틴이 맡은 경로의 단계는 계획에 올라오지 않는다 — 루틴 칸이 그 경로를 연다.
    assert [task["title"] for task in plan["tasks"] if "D-" in task["title"]] == []
    assert [row["title"] for row in plan["routines"]] == ["코딩테스트"]
    assert plan["routines"][0]["next_step"]["title"] == "D-3"


def test_without_a_routine_the_dated_steps_still_come_up(db_session):
    today = date.today()
    _path_of_three_days(db_session, today)

    plan = today_service.generate_plan(db_session, available_minutes=600, today=today)

    assert [task for task in plan["tasks"] if "D-" in task["title"]]
