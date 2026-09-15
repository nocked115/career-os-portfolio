"""Review 의 잔디 — 날마다 끝낸 것의 개수."""

from datetime import date, datetime

from app import models
from app.services import review


def _world(db):
    skill = models.Skill(name="Machine Learning", category="ai")
    db.add(skill); db.flush()

    book = models.LearningResource(title="핸즈온 ML", resource_type="book",
                                   ownership="owned", skill_id=skill.id)
    path = models.LearningPath(title="ML 기초", skill_id=skill.id)
    db.add_all([book, path]); db.flush()

    step = models.LearningStep(learning_path_id=path.id, title="분류", position=0,
                               status="completed", completed_at=datetime(2026, 9, 3, 21))
    db.add_all([
        models.LearningResourceSegment(learning_resource_id=book.id, position=0, label="1장",
                                       status="completed", completed_at=datetime(2026, 9, 3, 20)),
        models.LearningResourceSegment(learning_resource_id=book.id, position=1, label="2장",
                                       status="completed", completed_at=datetime(2026, 9, 10, 9)),
        step,
    ])
    db.flush()

    # 학습 단계에 딸린 할 일 — 단계와 같은 일이다
    db.add(models.DailyPlanTask(plan_date=date(2026, 9, 3), position=0, task_type="learning_step",
                                title="분류", minutes=45, reason="t", status="done",
                                completed_at=datetime(2026, 9, 3, 21), learning_step_id=step.id))
    # 따로 한 할 일
    db.add(models.DailyPlanTask(plan_date=date(2026, 9, 3), position=1, task_type="project",
                                title="프로젝트", minutes=45, reason="t", status="done",
                                completed_at=datetime(2026, 9, 3, 22)))
    db.add(models.SkillLevelEvent(skill_id=skill.id, from_level=0, to_level=1,
                                  changed_at=datetime(2026, 9, 3, 23)))
    # 다른 달
    db.add(models.LearningResourceSegment(learning_resource_id=book.id, position=2, label="3장",
                                          status="completed", completed_at=datetime(2026, 10, 1, 1)))
    db.commit()


def _day(result, d):
    return next(x for x in result["days"] if x["date"] == d)


def test_every_day_of_the_month_gets_a_cell(db_session):
    _world(db_session)
    assert len(review.build_activity(db_session, 2026, 9)["days"]) == 30


def test_step_and_its_task_are_counted_once(db_session):
    """할 일을 완료하면 단계도 완료된다. 둘을 따로 세면 한 일이 2개가 된다."""
    _world(db_session)
    d = _day(review.build_activity(db_session, 2026, 9), "2026-09-03")

    # 1장 + 분류(단계) + 프로젝트(할 일) + 레벨 = 4. 분류 할 일은 빠진다.
    assert d["count"] == 4
    assert [i["title"] for i in d["items"]].count("분류") == 1


def test_colour_buckets(db_session):
    _world(db_session)
    r = review.build_activity(db_session, 2026, 9)

    assert _day(r, "2026-09-03")["level"] == 3   # 4개 이상
    assert _day(r, "2026-09-10")["level"] == 1   # 1개
    assert _day(r, "2026-09-11")["level"] == 0   # 없음


def test_other_months_do_not_leak_in(db_session):
    _world(db_session)
    r = review.build_activity(db_session, 2026, 9)

    assert r["active_days"] == 2
    assert r["total"] == 5


def test_endpoint(client, db_session):
    _world(db_session)
    body = client.get("/analytics/activity?year=2026&month=9").json()

    assert body["active_days"] == 2
    assert client.get("/analytics/activity?year=2026").status_code == 422
