"""낡은 계획 — 세운 뒤 1위가 바뀌거나 기회가 들어오면 말한다."""

from datetime import date, datetime, timedelta

from app import models
from app.services import today as today_service


def _skill(db, name, level):
    skill = models.Skill(name=name, category="ai", level=level)
    db.add(skill)
    db.flush()
    return skill


def _opportunity(db, title, skills, collected_at=None):
    opportunity = models.Opportunity(
        source="manual", title=title, opportunity_type="job", skills=skills,
        **({"collected_at": collected_at} if collected_at else {}),
    )
    db.add(opportunity)
    return opportunity


def test_new_postings_that_change_the_leader_make_the_plan_outdated(db_session):
    ml = _skill(db_session, "Machine Learning", 1)
    torch = _skill(db_session, "PyTorch", 0)
    long_ago = datetime.now() - timedelta(days=3)
    _opportunity(db_session, "ML 공고", [ml], collected_at=long_ago)
    # 오늘 계획에 할 일이 하나는 있어야 낡았는지 말할 수 있다.
    db_session.add(models.LearningResource(title="핸즈온 머신러닝", resource_type="book", skill_id=ml.id))
    db_session.commit()

    plan = today_service.generate_plan(db_session, 120, "normal", today=date.today())
    assert plan["tasks"], "계획에 할 일이 있어야 한다"
    assert plan["outdated"] is None

    # 계획을 세운 뒤 PyTorch 를 요구하는 공고가 들어온다.
    # (DB 기본 시각은 UTC 라 시간대와 무관하게 확실히 과거로 둔다.)
    for task in db_session.query(models.DailyPlanTask).all():
        task.created_at = datetime.now() - timedelta(days=2)
    for index in range(3):
        _opportunity(db_session, f"PyTorch 공고 {index}", [torch])
    db_session.commit()

    outdated = today_service.build_plan(db_session, today=date.today())["outdated"]

    assert outdated["focus_before"] == "Machine Learning"
    assert outdated["focus_now"] == "PyTorch"
    assert outdated["reasons"] == [
        "우선순위 1위가 바뀌었어요 (Machine Learning → PyTorch)",
        "기회가 3건 새로 들어왔어요",
    ]

    rebuilt = today_service.generate_plan(db_session, 120, "normal", today=date.today())
    assert rebuilt["outdated"] is None


def test_a_day_without_planned_tasks_says_nothing(db_session):
    _skill(db_session, "SQL", 2)
    db_session.commit()

    assert today_service.build_plan(db_session, today=date.today())["outdated"] is None
