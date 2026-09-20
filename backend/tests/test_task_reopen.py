"""잘못 누른 완료는 되돌린다 — 완료가 남긴 기록까지."""

from datetime import date

from app import models


def _routine_task(db, **routine_fields):
    routine = models.Routine(
        title="코딩테스트", minutes=30, weekdays="0123456",
        target_count=3, unit_label="문제", active=True, **routine_fields,
    )
    db.add(routine)
    db.flush()

    task = models.DailyPlanTask(
        plan_date=date.today(), position=0, task_type="routine", title="코딩테스트",
        minutes=30, reason="매일", status="planned", routine_id=routine.id,
    )
    db.add(task)
    db.commit()
    return routine, task


def test_undoing_a_routine_removes_the_days_log(client, db_session):
    routine, task = _routine_task(db_session)

    assert client.post(f"/today/tasks/{task.id}/complete", json={"count": 3}).status_code == 200
    assert client.get("/routines").json()["routines"][0]["today_log"] == {"count": 3}

    undone = client.post(f"/today/tasks/{task.id}/reopen")

    assert undone.status_code == 200
    assert undone.json()["task"]["status"] == "planned"
    assert client.get("/routines").json()["routines"][0]["today_log"] is None


def test_a_step_finished_by_the_task_goes_back_to_in_progress(client, db_session):
    path = models.LearningPath(title="경로")
    db_session.add(path)
    db_session.flush()
    step = models.LearningStep(learning_path_id=path.id, title="단계", position=0)
    db_session.add(step)
    db_session.flush()
    task = models.DailyPlanTask(
        plan_date=date.today(), position=0, task_type="learning_step", title="단계",
        minutes=30, reason="이유", status="planned", learning_step_id=step.id,
    )
    db_session.add(task)
    db_session.commit()

    client.post(f"/today/tasks/{task.id}/complete")
    db_session.refresh(step)
    assert step.status == "completed"

    client.post(f"/today/tasks/{task.id}/reopen")
    db_session.refresh(step)

    assert step.status == "in_progress"
    assert step.completed_at is None


def test_a_skip_can_be_undone_and_planned_cannot(client, db_session):
    _, task = _routine_task(db_session)

    assert client.post(f"/today/tasks/{task.id}/reopen").status_code == 400

    client.post(f"/today/tasks/{task.id}/skip")
    assert client.post(f"/today/tasks/{task.id}/reopen").json()["task"]["status"] == "planned"


def test_linking_a_path_after_planning_is_seen_right_away(client, db_session):
    routine, task = _routine_task(db_session)
    path = models.LearningPath(title="SKT 코테")
    db_session.add(path)
    db_session.flush()
    db_session.add(models.LearningStep(learning_path_id=path.id, title="D-3", position=0))
    db_session.commit()

    client.patch(f"/routines/{routine.id}", json={"learning_path_id": path.id})

    tasks = client.get("/today/plan").json()["tasks"]
    summary = next(item for item in tasks if item["id"] == task.id)["routine"]

    assert summary["next_step"]["title"] == "D-3"
    assert summary["learning_path"]["title"] == "SKT 코테"
