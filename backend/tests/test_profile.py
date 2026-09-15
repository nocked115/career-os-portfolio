"""Profile — 화면 가운데 있어야 할 사람."""


def test_profile_starts_empty_and_does_not_invent_a_name(client):
    body = client.get("/profile").json()

    assert body["name"] == ""
    assert body["has_name"] is False


def test_profile_is_a_singleton(client):
    """1인용이다. 여러 번 읽어도 하나여야 한다."""
    client.get("/profile")
    client.get("/profile")

    client.patch("/profile", json={"name": "Hyun"})

    assert client.get("/profile").json()["name"] == "Hyun"


def test_profile_carries_the_target_and_the_focus(client):
    """가운데에는 이름만이 아니라 방향과 지금 할 것이 같이 있다."""
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    client.post(
        "/target-careers",
        json={"title": "Data / AI", "is_active": True},
    )

    body = client.get("/profile").json()

    assert body["target_career"] == "Data / AI"
    assert body["focus_skill"] == "AWS"
    assert body["priority_score"] > 0


def test_week_counts_only_completed_plan_tasks(client):
    """주간 누적은 새로 기록하지 않는다.

    완료한 계획 항목을 더한다. 계획을 세우기만 하고 끝내지 않으면
    0분이다 — 계획은 노력이 아니다.
    """
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    path = client.post(
        "/learning-paths",
        json={"title": "AWS 배포 익히기", "skill_id": skill["id"]},
    ).json()
    client.post(
        "/learning-steps",
        json={
            "learning_path_id": path["id"],
            "title": "EC2 기초",
            "estimated_minutes": 30,
            "position": 0,
        },
    )

    plan = client.post(
        "/today/plan?available_minutes=60&intensity=normal"
    ).json()
    assert plan["total_tasks"] > 0

    # 아직 아무것도 끝내지 않았다
    assert client.get("/profile").json()["week"]["minutes"] == 0

    task = plan["tasks"][0]
    client.post(f"/today/tasks/{task['id']}/complete")

    week = client.get("/profile").json()["week"]

    assert week["minutes"] == task["minutes"]
    assert week["completed_tasks"] == 1
    assert week["active_days"] == 1


def test_week_says_what_it_cannot_see(client):
    """계획 밖의 공부는 세지 못한다. 그렇다고 말한다."""
    note = client.get("/profile").json()["week"]["note"]

    assert "계획 밖" in note
