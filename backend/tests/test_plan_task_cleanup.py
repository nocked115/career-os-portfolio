"""지워진 것을 가리키는 계획 항목.

실사용 배포본을 정리하다가 났다. 목업 지원서를 지웠더니 오늘
계획에 "지원 준비 — AI 데이터 분석 공모전" 이 남았다. 그 공고는
이미 없었다. 지어낸 할 일이다.
"""

from datetime import date

from app import models


def _application(db):
    opportunity = models.Opportunity(
        title="어떤 공고",
        organization="어떤회사",
        opportunity_type="job",
        source="manual",
    )
    db.add(opportunity)
    db.flush()

    application = models.Application(
        opportunity_id=opportunity.id, status="preparing"
    )
    db.add(application)
    db.commit()

    return opportunity, application


def _task(db, *, status="planned", **links):
    task = models.DailyPlanTask(
        plan_date=date.today(),
        position=0,
        task_type="application",
        title="지원 준비 — 어떤 공고",
        minutes=30,
        reason="테스트",
        status=status,
        **links,
    )
    db.add(task)
    db.commit()

    return task


def test_deleting_an_application_removes_its_unfinished_task(
    client, db_session
):
    _, application = _application(db_session)
    task = _task(db_session, application_id=application.id)

    response = client.delete(f"/applications/{application.id}")

    assert response.status_code == 200
    assert response.json()["plan_tasks"] == {"removed": 1, "kept": 0}

    assert db_session.get(models.DailyPlanTask, task.id) is None


def test_a_finished_task_survives_but_loses_the_link(client, db_session):
    """그날 무엇을 했는지는 대상이 사라졌다고 없어질 기록이 아니다."""
    _, application = _application(db_session)
    task = _task(db_session, application_id=application.id, status="done")

    response = client.delete(f"/applications/{application.id}")

    assert response.json()["plan_tasks"] == {"removed": 0, "kept": 1}

    db_session.refresh(task)

    assert task.application_id is None
    # 제목은 만들 때 같이 저장하므로 연결이 끊겨도 읽힌다.
    assert task.title == "지원 준비 — 어떤 공고"


def test_deleting_an_opportunity_cleans_its_task_too(client, db_session):
    """지원서 없이도 계획에 오른다 — 마감 임박 "지원할지 정하기"."""
    opportunity = models.Opportunity(
        title="마감 임박",
        organization="어떤회사",
        opportunity_type="job",
        source="manual",
    )
    db_session.add(opportunity)
    db_session.commit()

    task = _task(db_session, opportunity_id=opportunity.id)

    response = client.delete(f"/opportunities/{opportunity.id}")

    assert response.status_code == 200
    assert response.json()["plan_tasks"]["removed"] == 1
    assert db_session.get(models.DailyPlanTask, task.id) is None


def test_todays_plan_has_no_task_pointing_at_nothing(client, db_session):
    """화면에서 확인한다. 이게 실제로 났던 증상이다."""
    _, application = _application(db_session)
    _task(db_session, application_id=application.id)

    client.delete(f"/applications/{application.id}")

    plan = client.get("/today/plan").json()

    ids = {t.get("application_id") for t in plan["tasks"]}

    assert None not in ids or ids == {None}
    assert all(
        db_session.get(models.Application, i) is not None
        for i in ids
        if i is not None
    )


def test_other_tasks_are_untouched(client, db_session):
    _, application = _application(db_session)
    _task(db_session, application_id=application.id)

    unrelated = _task(db_session)  # 아무것도 안 가리킨다

    client.delete(f"/applications/{application.id}")

    assert db_session.get(models.DailyPlanTask, unrelated.id) is not None
