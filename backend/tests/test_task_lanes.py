"""오늘 할 일을 갈래로 묶는다.

task_type 만으로는 "학교 수업" 과 "따로 공부" 를 못 가른다 — 둘 다 learning_step 이다.
학습 경로의 kind 를 같이 봐야 갈라진다.
"""

from datetime import datetime, timedelta

from app import models


def _path_with_step(db_session, title, kind, days=3):
    path = models.LearningPath(title=title, kind=kind, status="in_progress")
    db_session.add(path)
    db_session.flush()
    db_session.add(models.LearningStep(
        learning_path_id=path.id,
        title="1주차",
        position=0,
        estimated_minutes=30,
        due_date=(datetime.now() + timedelta(days=days)).date(),
    ))
    db_session.commit()
    return path


def _lanes(plan):
    return {t["title"]: t["lane"] for t in plan["tasks"]}


def test_a_course_and_a_study_land_in_different_lanes(client, db_session):
    _path_with_step(db_session, "추천시스템", "course", days=3)
    _path_with_step(db_session, "Tave 논문 스터디", "self", days=4)

    plan = client.post("/today/plan?available_minutes=180&intensity=normal").json()
    lanes = _lanes(plan)

    assert lanes["추천시스템 — 1주차"] == "course"
    assert lanes["Tave 논문 스터디 — 1주차"] == "study"


def test_a_path_defaults_to_self_study(client, db_session):
    """kind 를 안 주면 따로 공부다. 학교 수업은 명시해야 한다."""
    path = models.LearningPath(title="핸즈온 머신러닝", status="in_progress")
    db_session.add(path)
    db_session.commit()

    assert path.kind == "self"


def test_an_opportunity_is_a_deciding_lane(client):
    client.post("/opportunities", json={
        "opportunity_type": "job", "title": "Data Analyst", "organization": "어딘가",
        "source": "manual", "status": "interested",
        "deadline": (datetime.now() + timedelta(days=2)).isoformat(),
    })

    plan = client.post("/today/plan?available_minutes=180&intensity=normal").json()

    lanes = [t["lane"] for t in plan["tasks"] if t["task_type"] == "opportunity"]
    assert lanes == ["deciding"]


def test_every_line_carries_a_label(client, db_session):
    _path_with_step(db_session, "추천시스템", "course")

    plan = client.post("/today/plan?available_minutes=180&intensity=normal").json()

    for task in plan["tasks"]:
        assert task["lane_label"], "화면에 보일 갈래 이름이 있어야 한다"
