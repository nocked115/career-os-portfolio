"""끝낸 자리에서 받아 드는 영수증.

수현: "학습에서 완료표시를 했는데 ... 위에 크게 참 잘했어요 도장이라도
찍어주던지. 그리고 결과표를 내주던지 영수증처럼 — 총 걸린 시간 3시간
(예상 시간보다 00시간 오버) / 남긴 자료들 노션 등."

영수증의 조건은 하나다. **산 것만 적혀 있어야 한다.** 안 적은 시간을
0 분으로 적거나, 남긴 자료가 없는데 있는 척하면 그건 영수증이 아니라
상장이고, 상장은 나중에 경험으로 꺼낼 때 아무 쓸모가 없다.
"""

from datetime import date, timedelta

from app import models


TODAY = date.today()


def _path(db, title="Tave 논문 스터디"):
    path = models.LearningPath(title=title, description="매주 논문 한 편")
    db.add(path)
    db.flush()
    return path


def _step(db, path, title="3주차 A — 논문 정독", position=0, minutes=150):
    step = models.LearningStep(
        learning_path_id=path.id, title=title, position=position,
        estimated_minutes=minutes,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def _task(db, step, planned, actual=None, day_offset=0):
    task = models.DailyPlanTask(
        plan_date=TODAY - timedelta(days=day_offset), position=0,
        task_type="learning_step", title=step.title, minutes=planned,
        reason="", status="done", actual_minutes=actual,
        learning_step_id=step.id,
    )
    db.add(task)
    db.commit()
    return task


def test_the_receipt_adds_up_the_time_that_was_actually_recorded(client, db_session):
    path = _path(db_session)
    step = _step(db_session, path, minutes=150)
    _task(db_session, step, planned=50, actual=40, day_offset=2)
    _task(db_session, step, planned=50, actual=30, day_offset=0)

    receipt = client.post(f"/learning-steps/{step.id}/complete").json()["receipt"]

    assert receipt["estimated_minutes"] == 150
    assert receipt["actual_minutes"] == 70
    assert receipt["measured_days"] == 2
    assert receipt["gap_minutes"] == -80          # 예상보다 80분 덜 걸렸다
    assert receipt["span_days"] == 3              # 사흘에 걸쳐
    assert receipt["step"]["title"] == step.title
    assert receipt["path"]["title"] == "Tave 논문 스터디"


def test_unrecorded_time_is_none_and_not_zero(client, db_session):
    """0 분이라고 적으면 '한 번에 끝냈다' 는 거짓말이 된다."""
    path = _path(db_session)
    step = _step(db_session, path)
    _task(db_session, step, planned=50)           # 실제 시간 안 적음

    receipt = client.post(f"/learning-steps/{step.id}/complete").json()["receipt"]

    assert receipt["actual_minutes"] is None
    assert receipt["measured_days"] == 0
    assert receipt["gap_minutes"] is None


def test_one_recorded_day_among_several_counts_only_itself(client, db_session):
    path = _path(db_session)
    step = _step(db_session, path, minutes=100)
    _task(db_session, step, planned=50, actual=60, day_offset=1)
    _task(db_session, step, planned=50, day_offset=0)

    receipt = client.post(f"/learning-steps/{step.id}/complete").json()["receipt"]

    assert receipt["actual_minutes"] == 60
    assert receipt["measured_days"] == 1
    assert receipt["gap_minutes"] == -40


def test_the_receipt_names_what_is_blank_instead_of_filling_it(client, db_session):
    path = _path(db_session)
    step = _step(db_session, path)

    receipt = client.post(f"/learning-steps/{step.id}/complete").json()["receipt"]

    assert receipt["missing"] == ["걸린 시간", "남긴 자료"]
    assert receipt["outputs"] == []


def test_what_was_left_behind_is_listed(client, db_session):
    path = _path(db_session)
    step = _step(db_session, path)
    _task(db_session, step, planned=50, actual=55)
    client.post(f"/learning-steps/{step.id}/outputs", json={
        "title": "GLIP 요약", "url": "https://notion.so/glip",
    })

    receipt = client.post(f"/learning-steps/{step.id}/complete").json()["receipt"]

    assert [item["title"] for item in receipt["outputs"]] == ["GLIP 요약"]
    assert [item["url"] for item in receipt["outputs"]] == ["https://notion.so/glip"]
    assert receipt["missing"] == []


def test_the_receipt_counts_the_checklist_and_points_at_the_next_step(client, db_session):
    path = _path(db_session)
    step = _step(db_session, path, position=0)
    later = _step(db_session, path, title="4주차 — Latent Diffusion", position=1)
    db_session.add_all([
        models.LearningChecklistItem(
            learning_step_id=step.id, position=index, text=f"{index}쪽", done=index < 2
        )
        for index in range(3)
    ])
    db_session.commit()

    receipt = client.post(f"/learning-steps/{step.id}/complete").json()["receipt"]

    assert receipt["checked"] == 2
    assert receipt["total_items"] == 3
    assert receipt["next_step"]["title"] == later.title


def test_the_last_step_has_no_next(client, db_session):
    path = _path(db_session)
    step = _step(db_session, path)

    receipt = client.post(f"/learning-steps/{step.id}/complete").json()["receipt"]

    assert receipt["next_step"] is None
