"""공고 · 지원은 시간 예산과 자리를 먹지 않는다.

15분짜리 "지원할지 정하기" 가 예산과 max_tasks 를 먹으면 공고가 몇 건 들어온 날은
공부가 통째로 밀린다. 목록에는 그대로 둔다 — 마감은 놓치면 끝이다.
"""

from datetime import datetime, timedelta

from app import models


def _opportunity(client, title, days):
    return client.post("/opportunities", json={
        "opportunity_type": "job",
        "title": title,
        "organization": "어딘가",
        "source": "manual",
        "status": "interested",
        "deadline": (datetime.now() + timedelta(days=days)).isoformat(),
    }).json()


def test_opportunity_minutes_are_not_counted_as_planned(client):
    _opportunity(client, "지원 1", 2)

    plan = client.post("/today/plan?available_minutes=120&intensity=normal").json()

    lines = [t for t in plan["tasks"] if t["task_type"] == "opportunity"]
    assert lines, "공고 줄이 계획에 있어야 한다 — 빼는 게 아니라 안 세는 것이다"
    assert plan["planned_minutes"] == 0
    assert plan["remaining_minutes"] == 120


def _seed_steps(db_session, how_many=3):
    path = models.LearningPath(title="추천시스템", status="in_progress")
    db_session.add(path)
    db_session.flush()
    for i in range(how_many):
        db_session.add(models.LearningStep(
            learning_path_id=path.id,
            title=f"{i + 1}주차",
            position=i,
            estimated_minutes=30,
            due_date=(datetime.now() + timedelta(days=3 + i)).date(),
        ))
    db_session.commit()


def test_opportunities_do_not_take_the_study_slots(client, db_session):
    """공고가 몇 건 오든 공부가 받는 자리는 그대로다.

    마감 있는 학습은 설계상 하루 둘까지다 (MAX_DUE_LEARNING). 여기서 확인하는 것은
    "둘" 이 아니라 **공고가 그 둘을 깎지 않는다** 는 것이다.
    """
    _seed_steps(db_session)

    without = client.post("/today/plan?available_minutes=180&intensity=normal").json()
    study_before = [t for t in without["tasks"] if t["task_type"] == "learning_step"]
    minutes_before = without["planned_minutes"]

    for i in range(3):
        _opportunity(client, f"지원 {i}", 2)

    after = client.post("/today/plan?available_minutes=180&intensity=normal").json()
    study_after = [t for t in after["tasks"] if t["task_type"] == "learning_step"]
    opportunities = [t for t in after["tasks"] if t["task_type"] == "opportunity"]

    assert len(study_after) == len(study_before), "공고가 공부 자리를 먹지 않아야 한다"
    assert after["planned_minutes"] == minutes_before, "공고는 계획 시간에 안 들어간다"
    assert len(opportunities) == 3, "공고도 목록에는 다 보여야 한다"


def test_the_same_opportunity_does_not_appear_twice(client, db_session):
    """마감 후보와 이월 후보가 같은 공고를 가리키면 한 줄만 남아야 한다.

    공고를 예산 밖으로 빼면서 allocate 를 건너뛰게 했더니, allocate 가 max_tasks 로
    잘라주던 것이 중복까지 가려주고 있었다는 게 드러났다 — 같은 공고가
    "기회" 와 "기회 · 이월" 두 줄로 화면에 나왔다.
    """
    from datetime import date, timedelta

    row = _opportunity(client, "지원할지 정하기 대상", 2)

    # 어제 계획에 올라갔다가 못 끝낸 것처럼 만든다 → 오늘 이월 후보가 된다.
    client.post("/today/plan?available_minutes=120&intensity=normal")
    task = (
        db_session.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.opportunity_id == row["id"])
        .first()
    )
    assert task is not None
    task.plan_date = date.today() - timedelta(days=1)
    db_session.commit()

    plan = client.post("/today/plan?available_minutes=120&intensity=normal").json()

    # opportunity_id 로 세면 안 된다 — 이월 줄은 그 칸이 비어 있어서 하나만 세인다.
    # 화면에 보이는 것은 제목이므로 제목으로 센다.
    lines = [t for t in plan["tasks"] if "지원할지 정하기 대상" in (t.get("title") or "")]
    assert len(lines) == 1, [(t["title"], t["reason"]) for t in lines]
