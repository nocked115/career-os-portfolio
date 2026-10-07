"""오늘 계획에 직접 넣기 — 시간이 남아 하고 싶은 것을 넣을 자리."""

from datetime import date

from app import models


def test_a_project_can_be_added_by_hand(client, db_session):
    project = models.Project(name="캡스톤", status="in_progress", progress_percent=60)
    db_session.add(project)
    db_session.commit()

    body = client.post("/today/tasks", json={
        "kind": "project", "target_id": project.id, "minutes": 45,
    }).json()

    assert body["added"] is True
    task = next(t for t in body["plan"]["tasks"] if t["project_id"] == project.id)
    assert task["minutes"] == 45
    assert "직접 넣었습니다" in task["reason"]
    assert "60%" in task["reason"]


def test_the_same_thing_is_not_added_twice(client, db_session):
    project = models.Project(name="캡스톤", status="in_progress")
    db_session.add(project)
    db_session.commit()

    client.post("/today/tasks", json={"kind": "project", "target_id": project.id})
    again = client.post("/today/tasks", json={"kind": "project", "target_id": project.id}).json()

    assert again["added"] is False
    assert "이미 오늘 계획에 있어요" in again["reason"]


def test_a_free_line_needs_words(client):
    assert client.post("/today/tasks", json={"kind": "custom", "title": "  "}).status_code == 422

    body = client.post("/today/tasks", json={
        "kind": "custom", "title": "논문 초록 다시 읽기", "minutes": 20,
    }).json()

    assert [t["title"] for t in body["plan"]["tasks"]] == ["논문 초록 다시 읽기"]


def test_a_missing_target_says_so(client):
    assert client.post("/today/tasks", json={
        "kind": "learning_step", "target_id": 9999,
    }).status_code == 404


def test_a_hand_added_step_still_moves_its_progress(client, db_session):
    """직접 넣어도 완료하면 진행률이 같이 움직인다 — 가리키는 대상을 남기기 때문이다."""
    path = models.LearningPath(title="Tave")
    db_session.add(path)
    db_session.flush()
    step = models.LearningStep(learning_path_id=path.id, title="1주차", position=0)
    db_session.add(step)
    db_session.commit()

    body = client.post("/today/tasks", json={
        "kind": "learning_step", "target_id": step.id, "minutes": 60,
    }).json()
    task = next(t for t in body["plan"]["tasks"] if t["learning_step_id"] == step.id)

    client.post(f"/today/tasks/{task['id']}/complete")
    db_session.refresh(step)

    assert step.status == "completed"
