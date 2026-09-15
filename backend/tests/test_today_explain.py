"""Today 항목이 스스로를 설명하는가.

화면에는 "(점수 87)" 같은 원시 점수가 떠 있었고, 완료를 누르면 무엇이
바뀌는지는 눌러 봐야 알았다.
"""


def _skill(client, name, level=0):
    return client.post(
        "/skills", json={"name": name, "category": "x", "level": level}
    ).json()


def _demand(client, skills):
    job = client.post(
        "/jobs", json={"company": "A", "title": "T", "role": "r"}
    ).json()
    for skill in skills:
        client.post(f"/jobs/{job['id']}/skills/{skill['id']}")


def _path(client, skill, steps):
    path = client.post(
        "/learning-paths", json={"title": "AWS 배포", "skill_id": skill["id"]}
    ).json()

    created = [
        client.post(
            "/learning-steps",
            json={
                "learning_path_id": path["id"],
                "title": title,
                "position": index,
                "estimated_minutes": 30,
            },
        ).json()
        for index, title in enumerate(steps)
    ]

    return path, created


def test_the_reason_uses_evidence_not_a_raw_score(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path(client, aws, ["EC2 Fundamentals"])

    task = client.post("/today/plan").json()["tasks"][0]

    assert "우선순위 1위" in task["reason"]
    assert "기회 1건 중 1건" in task["reason"]
    assert "레벨 0/4" in task["reason"]
    assert "점수" not in task["reason"]


def test_tasks_carry_a_korean_area(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path(client, aws, ["EC2 Fundamentals"])

    task = client.post("/today/plan").json()["tasks"][0]

    assert task["area"] == "학습"


def test_the_completion_preview_matches_what_actually_happens(client):
    """누르기 전에 말한 진행률이 누른 뒤의 진행률과 같아야 한다."""
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    path, _ = _path(client, aws, ["EC2", "S3", "IAM", "배포"])

    task = client.post("/today/plan").json()["tasks"][0]

    assert "0% → 25%" in task["on_complete"]

    client.post(f"/today/tasks/{task['id']}/complete")

    after = client.get(f"/learning-paths/{path['id']}").json()
    assert after["progress_percent"] == 25


def test_things_that_do_not_change_say_so(client, db_session):
    """프로젝트 체크 한 번에 진행률이 오를 거라고 기대하게 두지 않는다."""
    from datetime import date

    from app import models
    from app.services import today as today_service

    project = models.Project(name="배포 프로젝트", career_related=True)
    db_session.add(project)
    db_session.flush()

    task = models.DailyPlanTask(
        plan_date=date.today(), position=0, task_type="project",
        title="배포 프로젝트", minutes=45, reason="진행 중", status="planned",
        project_id=project.id,
    )
    db_session.add(task)
    db_session.commit()

    preview = today_service.preview_completion(task)

    assert "직접 올려" in preview
