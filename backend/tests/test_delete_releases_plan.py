"""지울 때 남는 것 — 끝낸 기록은 남기고, 없는 것을 가리키는 할 일은 치운다."""

from datetime import date

from app import models


def _task(db, status, **link):
    task = models.DailyPlanTask(
        plan_date=date(2026, 9, 16), position=0, task_type="project",
        title="할 일", minutes=30, reason="테스트", status=status, **link,
    )
    db.add(task)
    return task


def test_deleting_a_project_keeps_the_skill_and_evidence(client, db_session):
    skill = models.Skill(name="AWS", category="cloud", level=1)
    project = models.Project(name="AWS Mini Project", skills=[skill])
    db_session.add_all([skill, project])
    db_session.flush()

    experience = models.Experience(
        experience_type="project", title="AWS 배포 경험", project_id=project.id
    )
    db_session.add(experience)
    done = _task(db_session, "done", project_id=project.id)
    _task(db_session, "planned", project_id=project.id)
    db_session.commit()

    body = client.delete(f"/projects/{project.id}").json()

    assert body["plan_tasks"] == {"removed": 1, "kept": 1}
    assert body["unlinked_evidence"] == 1
    db_session.expire_all()
    assert db_session.get(models.Skill, skill.id) is not None
    assert db_session.get(models.Experience, experience.id).project_id is None
    assert db_session.get(models.DailyPlanTask, done.id).project_id is None
    assert client.delete(f"/projects/{project.id}").status_code == 404


def test_deleting_a_path_releases_step_tasks_and_routines(client, db_session):
    path = models.LearningPath(title="AWS 배포 익히기")
    db_session.add(path)
    db_session.flush()
    step = models.LearningStep(learning_path_id=path.id, title="EC2", position=0)
    routine = models.Routine(title="rehab", learning_path_id=path.id)
    db_session.add_all([step, routine])
    db_session.flush()
    _task(db_session, "planned", learning_step_id=step.id)
    db_session.commit()

    body = client.delete(f"/learning-paths/{path.id}").json()

    assert body["plan_tasks"] == {"removed": 1, "kept": 0}
    db_session.expire_all()
    assert db_session.get(models.Routine, routine.id).learning_path_id is None


def test_deleting_a_resource_releases_its_tasks(client, db_session):
    skill = models.Skill(name="AWS", category="cloud", level=1)
    db_session.add(skill)
    db_session.flush()
    resource = models.LearningResource(
        title="AWS 완벽 가이드", resource_type="book", skill_id=skill.id
    )
    db_session.add(resource)
    db_session.flush()
    _task(db_session, "done", learning_resource_id=resource.id)
    db_session.commit()

    body = client.delete(f"/resources/{resource.id}").json()

    assert body["plan_tasks"] == {"removed": 0, "kept": 1}
