"""Learning Path / Step API (SPEC 7~9장)."""


def _make_path(client, title="AWS", skill_id=None):
    payload = {"title": title}

    if skill_id is not None:
        payload["skill_id"] = skill_id

    response = client.post("/learning-paths", json=payload)
    assert response.status_code == 201

    return response.json()


def test_create_and_read_learning_path(client):
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud"},
    ).json()

    path = _make_path(client, skill_id=skill["id"])

    assert path["status"] == "not_started"
    assert path["progress_percent"] == 0
    assert path["skill_id"] == skill["id"]

    assert client.get(f"/learning-paths/{path['id']}").status_code == 200
    assert len(client.get("/learning-paths").json()) == 1
    assert len(client.get(f"/learning-paths?skill_id={skill['id']}").json()) == 1


def test_learning_path_rejects_unknown_skill(client):
    response = client.post(
        "/learning-paths",
        json={"title": "X", "skill_id": 999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill not found"


def test_patch_only_changes_sent_fields(client):
    path = _make_path(client)

    updated = client.patch(
        f"/learning-paths/{path['id']}",
        json={"progress_percent": 40},
    ).json()

    assert updated["progress_percent"] == 40
    assert updated["title"] == "AWS"
    assert updated["status"] == "not_started"


def test_invalid_status_is_rejected(client):
    path = _make_path(client)

    response = client.patch(
        f"/learning-paths/{path['id']}",
        json={"status": "완료함"},
    )

    assert response.status_code == 422


def test_progress_percent_bounds(client):
    response = client.post(
        "/learning-paths",
        json={"title": "X", "progress_percent": 120},
    )

    assert response.status_code == 422


def test_duplicate_step_position_returns_409(client):
    path = _make_path(client)

    first = client.post(
        "/learning-steps",
        json={
            "learning_path_id": path["id"],
            "title": "EC2",
            "position": 0,
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/learning-steps",
        json={
            "learning_path_id": path["id"],
            "title": "S3",
            "position": 0,
        },
    )

    assert second.status_code == 409


def test_steps_are_listed_in_position_order(client):
    path = _make_path(client)

    for position, title in [(2, "IAM"), (0, "EC2"), (1, "S3")]:
        client.post(
            "/learning-steps",
            json={
                "learning_path_id": path["id"],
                "title": title,
                "position": position,
            },
        )

    titles = [
        step["title"]
        for step in client.get(
            f"/learning-steps?learning_path_id={path['id']}"
        ).json()
    ]

    assert titles == ["EC2", "S3", "IAM"]


def test_progress_rolls_up_from_steps(client):
    """SPEC 9장: 스텝 완료가 경로 진행률로 올라와야 한다."""
    path = _make_path(client)

    steps = []

    for position, title in enumerate(["EC2", "S3", "IAM", "Docker"]):
        steps.append(
            client.post(
                "/learning-steps",
                json={
                    "learning_path_id": path["id"],
                    "title": title,
                    "position": position,
                },
            ).json()
        )

    body = client.get(f"/learning-paths/{path['id']}/progress").json()
    assert body["progress_percent"] == 0
    assert body["status"] == "not_started"

    client.patch(
        f"/learning-steps/{steps[0]['id']}",
        json={"status": "completed"},
    )

    body = client.get(f"/learning-paths/{path['id']}/progress").json()
    assert body["completed_steps"] == 1
    assert body["progress_percent"] == 25
    assert body["status"] == "in_progress"

    for step in steps[1:]:
        client.patch(
            f"/learning-steps/{step['id']}",
            json={"status": "completed"},
        )

    body = client.get(f"/learning-paths/{path['id']}/progress").json()
    assert body["progress_percent"] == 100
    assert body["status"] == "completed"

    # 계산 결과가 실제로 저장되는지
    stored = client.get(f"/learning-paths/{path['id']}").json()
    assert stored["progress_percent"] == 100
    assert stored["status"] == "completed"


def test_progress_on_empty_path(client):
    path = _make_path(client)

    body = client.get(f"/learning-paths/{path['id']}/progress").json()

    assert body["total_steps"] == 0
    assert body["progress_percent"] == 0


def test_step_resource_linking(client):
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud"},
    ).json()

    resource = client.post(
        "/resources",
        json={
            "title": "EC2 Docs",
            "url": "https://example.com",
            "skill_id": skill["id"],
        },
    ).json()

    path = _make_path(client, skill_id=skill["id"])

    step = client.post(
        "/learning-steps",
        json={
            "learning_path_id": path["id"],
            "title": "EC2",
            "position": 0,
        },
    ).json()

    link = client.post(
        f"/learning-steps/{step['id']}/resources/{resource['id']}"
    )
    assert link.status_code == 200

    listed = client.get(f"/learning-steps/{step['id']}/resources").json()
    assert [r["title"] for r in listed] == ["EC2 Docs"]

    # 같은 자료를 두 번 연결해도 중복되지 않는다
    client.post(f"/learning-steps/{step['id']}/resources/{resource['id']}")
    assert len(client.get(f"/learning-steps/{step['id']}/resources").json()) == 1

    client.delete(f"/learning-steps/{step['id']}/resources/{resource['id']}")
    assert client.get(f"/learning-steps/{step['id']}/resources").json() == []


def test_deleting_path_removes_its_steps(client):
    path = _make_path(client)

    client.post(
        "/learning-steps",
        json={
            "learning_path_id": path["id"],
            "title": "EC2",
            "position": 0,
        },
    )

    client.delete(f"/learning-paths/{path['id']}")

    assert client.get(f"/learning-paths/{path['id']}").status_code == 404
    assert client.get("/learning-steps").json() == []
