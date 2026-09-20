"""루틴이 맡은 경로는 계획이 따로 넣지 않는다.

하루에 한 단계씩 짠 사흘짜리 계획에서, 오늘 것은 루틴이 올리고
내일 · 모레 것은 "마감 있는 학습" 이 올려 하루에 사흘이 다 들어왔다.
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


def test_only_the_routine_brings_todays_step(db_session):
    today = date.today()
    path = _path_of_three_days(db_session, today)

    db_session.add(models.Routine(
        title="코딩테스트", minutes=30, weekdays="0123456",
        learning_path_id=path.id, active=True,
    ))
    db_session.commit()

    plan = today_service.generate_plan(db_session, available_minutes=600, today=today)
    from_this_path = [
        task["title"] for task in plan["tasks"] if "D-" in task["title"]
    ]

    assert len(from_this_path) == 1
    assert from_this_path[0].startswith("코딩테스트")


def test_without_a_routine_the_dated_steps_still_come_up(db_session):
    today = date.today()
    _path_of_three_days(db_session, today)

    plan = today_service.generate_plan(db_session, available_minutes=600, today=today)

    assert [task for task in plan["tasks"] if "D-" in task["title"]]
