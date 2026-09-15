"""학습을 끝냈을 때 무엇이 바뀌었는지 말하는가.

전에는 완료 뒤 "반영되었습니다" 한 줄뿐이었다. 세션에서 끝낸 단계가
오늘 계획에는 여전히 할 일로 남아 있기도 했다.
"""


def _skill(client, name="AWS"):
    return client.post(
        "/skills", json={"name": name, "category": "x", "level": 0}
    ).json()


def _path(client, skill, titles):
    path = client.post(
        "/learning-paths", json={"title": "AWS 배포", "skill_id": skill["id"]}
    ).json()

    steps = [
        client.post(
            "/learning-steps",
            json={
                "learning_path_id": path["id"],
                "title": title,
                "position": index,
                "estimated_minutes": 30,
            },
        ).json()
        for index, title in enumerate(titles)
    ]

    return path, steps


def test_completing_reports_before_and_after(client):
    skill = _skill(client)
    _, steps = _path(client, skill, ["EC2", "S3"])

    body = client.post(f"/learning-steps/{steps[0]['id']}/complete").json()

    assert body["learning_path"]["progress_before"] == 0
    assert body["learning_path"]["progress_percent"] == 50
    assert "0% → 50%" in " ".join(body["effects"])
    assert body["next_step"]["title"] == "S3"


def test_completing_twice_does_not_claim_new_progress(client):
    skill = _skill(client)
    _, steps = _path(client, skill, ["EC2", "S3"])

    client.post(f"/learning-steps/{steps[0]['id']}/complete")
    again = client.post(f"/learning-steps/{steps[0]['id']}/complete").json()

    assert again["already_completed"] is True
    assert not any("→" in effect for effect in again["effects"])


def test_finishing_in_a_session_also_finishes_the_today_task(client):
    """세션에서 끝냈는데 Today 에 할 일로 남으면 두 화면이 다른 말을 한다."""
    skill = _skill(client)
    _, steps = _path(client, skill, ["EC2"])

    task = client.post("/today/plan").json()["tasks"][0]
    assert task["learning_step_id"] == steps[0]["id"]

    body = client.post(f"/learning-steps/{steps[0]['id']}/complete").json()

    assert "오늘 계획" in " ".join(body["effects"])

    after = client.get("/today/plan").json()["tasks"][0]
    assert after["status"] == "done"


def test_the_library_shows_which_steps_use_a_resource(client):
    skill = _skill(client)
    _, steps = _path(client, skill, ["EC2"])

    resource = client.post(
        "/resources",
        json={
            "title": "AWS 교재",
            "resource_type": "book",
            "ownership": "owned",
            "url": None,
            "skill_id": skill["id"],
        },
    ).json()

    client.post(f"/learning-steps/{steps[0]['id']}/resources/{resource['id']}")

    items = client.get("/library").json()["items"]
    linked = next(item for item in items if item["id"] == resource["id"])

    assert [step["title"] for step in linked["linked_steps"]] == ["EC2"]
