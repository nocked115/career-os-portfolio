"""Mission 022 - Learning Session / 자료 중요도."""


def _setup_session(client, *, with_job=True, description=""):
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 1},
    ).json()

    if with_job:
        job = client.post(
            "/jobs",
            json={"company": "A", "title": "T", "role": "r"},
        ).json()
        client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    path = client.post(
        "/learning-paths",
        json={"title": "AWS Path", "skill_id": skill["id"]},
    ).json()

    step = client.post(
        "/learning-steps",
        json={
            "learning_path_id": path["id"],
            "title": "EC2 Fundamentals",
            "description": description,
            "position": 0,
            "estimated_minutes": 45,
        },
    ).json()

    return skill, path, step


# --------------------------------
# 자료 종류 / 중요도
# --------------------------------

def test_resource_type_is_validated(client):
    skill = client.post(
        "/skills", json={"name": "AWS", "category": "cloud"}
    ).json()

    bad = client.post(
        "/resources",
        json={
            "title": "X",
            "url": "https://example.com",
            "resource_type": "youtube",
            "skill_id": skill["id"],
        },
    )
    assert bad.status_code == 422

    good = client.post(
        "/resources",
        json={
            "title": "X",
            "url": "https://example.com",
            "resource_type": "official_doc",
            "skill_id": skill["id"],
        },
    )
    assert good.status_code == 200
    assert good.json()["resource_type"] == "official_doc"


def test_resource_importance_defaults_to_primary(client):
    skill = client.post(
        "/skills", json={"name": "AWS", "category": "cloud"}
    ).json()

    resource = client.post(
        "/resources",
        json={
            "title": "X",
            "url": "https://example.com",
            "skill_id": skill["id"],
        },
    ).json()

    assert resource["importance"] == "primary"
    assert resource["resource_type"] == "video"


def test_resource_importance_is_validated(client):
    skill = client.post(
        "/skills", json={"name": "AWS", "category": "cloud"}
    ).json()

    response = client.post(
        "/resources",
        json={
            "title": "X",
            "url": "https://example.com",
            "importance": "very_important",
            "skill_id": skill["id"],
        },
    )
    assert response.status_code == 422


def test_resource_can_be_updated_and_deleted(client):
    skill = client.post(
        "/skills", json={"name": "AWS", "category": "cloud"}
    ).json()

    resource = client.post(
        "/resources",
        json={
            "title": "X",
            "url": "https://example.com",
            "skill_id": skill["id"],
        },
    ).json()

    updated = client.patch(
        f"/resources/{resource['id']}",
        json={"importance": "deep_dive"},
    )
    assert updated.status_code == 200
    assert updated.json()["importance"] == "deep_dive"
    assert updated.json()["title"] == "X"

    assert client.delete(f"/resources/{resource['id']}").status_code == 200
    assert client.get("/resources").json() == []


# --------------------------------
# Session 구성
# --------------------------------

def test_session_returns_step_path_and_skill(client):
    skill, path, step = _setup_session(client)

    body = client.get(f"/learning-steps/{step['id']}/session").json()

    assert body["step"]["title"] == "EC2 Fundamentals"
    assert body["step"]["estimated_minutes"] == 45
    assert body["learning_path"]["title"] == "AWS Path"
    assert body["skill"]["name"] == "AWS"


def test_session_goals_come_from_description_only(client):
    """목표는 설명에 적힌 것만. 지어내지 않는다."""
    description = "- EC2 가 무엇인지 설명하기\n- Region 과 AZ 구분하기"

    skill, path, step = _setup_session(client, description=description)

    body = client.get(f"/learning-steps/{step['id']}/session").json()

    assert body["goals"] == [
        "EC2 가 무엇인지 설명하기",
        "Region 과 AZ 구분하기",
    ]


def test_session_goals_empty_when_no_description(client):
    skill, path, step = _setup_session(client)

    body = client.get(f"/learning-steps/{step['id']}/session").json()

    assert body["goals"] == []


def test_session_groups_materials_by_importance(client):
    skill, path, step = _setup_session(client)

    for title, importance, minutes in (
        ("공식 문서", "primary", 15),
        ("실습", "primary", 20),
        ("책 3장", "supplementary", 15),
        ("백서", "deep_dive", 60),
    ):
        resource = client.post(
            "/resources",
            json={
                "title": title,
                "url": f"https://example.com/{title}",
                "duration_minutes": minutes,
                "importance": importance,
                "skill_id": skill["id"],
            },
        ).json()

        client.post(
            f"/learning-steps/{step['id']}/resources/{resource['id']}"
        )

    body = client.get(f"/learning-steps/{step['id']}/session").json()

    assert [m["title"] for m in body["materials"]["primary"]] == [
        "공식 문서",
        "실습",
    ]
    assert [m["title"] for m in body["materials"]["supplementary"]] == ["책 3장"]
    assert [m["title"] for m in body["materials"]["deep_dive"]] == ["백서"]
    assert body["material_minutes"] == 110


def test_why_now_is_grounded_in_real_data(client):
    skill, path, step = _setup_session(client)

    why = client.get(
        f"/learning-steps/{step['id']}/session"
    ).json()["why_now"]

    assert why["skill"] == "AWS"
    assert why["priority_rank"] == 1
    assert why["total_demand"] == 1
    assert why["demand_requiring"] == 1
    assert why["my_level"] == 1
    assert why["has_project_evidence"] is False

    text = " ".join(why["reasons"])
    assert "1건" in text
    assert "레벨은 1" in text
    assert "프로젝트 증거가 아직 없습니다" in text


def test_why_now_says_so_when_there_is_no_market_data(client):
    """공고가 없으면 수요를 지어내지 않고 없다고 말한다."""
    skill, path, step = _setup_session(client, with_job=False)

    why = client.get(
        f"/learning-steps/{step['id']}/session"
    ).json()["why_now"]

    assert why["total_demand"] == 0
    assert why["market_percentage"] == 0
    assert "계산할 수 없습니다" in " ".join(why["reasons"])


# --------------------------------
# 시작 / 완료
# --------------------------------

def test_start_marks_step_in_progress(client):
    skill, path, step = _setup_session(client)

    body = client.post(f"/learning-steps/{step['id']}/start").json()

    assert body["step"]["status"] == "in_progress"
    assert client.get(
        f"/learning-paths/{path['id']}"
    ).json()["status"] == "in_progress"


def test_complete_updates_step_and_path(client):
    skill, path, step = _setup_session(client)

    body = client.post(f"/learning-steps/{step['id']}/complete").json()

    assert body["status"] == "completed"
    assert body["completed_at"] is not None
    assert body["learning_path"]["progress_percent"] == 100
    assert body["learning_path"]["completed_steps"] == 1
    assert body["learning_path"]["total_steps"] == 1


def test_complete_flows_through_to_priority(client):
    """완료 한 번으로 우선순위까지 내려가야 한다."""
    skill, path, step = _setup_session(client)

    before = client.get(
        "/analytics/learning-priority"
    ).json()["learning_priority"][0]["priority_score"]

    client.post(f"/learning-steps/{step['id']}/complete")

    after = client.get(
        "/analytics/learning-priority"
    ).json()["learning_priority"][0]["priority_score"]

    assert after < before
    assert after == round(before * 0.6)


# --------------------------------
# Today 연결
# --------------------------------

def test_today_points_at_the_next_learning_step(client):
    skill, path, step = _setup_session(client)

    body = client.get("/today").json()

    assert body["focus_skill"] == "AWS"
    assert body["next_learning_step"]["step_id"] == step["id"]
    assert body["next_learning_step"]["title"] == "EC2 Fundamentals"
    assert body["next_learning_step"]["session_url"] == (
        f"/learning-steps/{step['id']}/session"
    )


def test_today_skips_completed_steps(client):
    skill, path, first = _setup_session(client)

    second = client.post(
        "/learning-steps",
        json={
            "learning_path_id": path["id"],
            "title": "S3 Basics",
            "position": 1,
        },
    ).json()

    client.post(f"/learning-steps/{first['id']}/complete")

    body = client.get("/today").json()

    assert body["next_learning_step"]["step_id"] == second["id"]


def test_today_has_no_step_when_there_is_no_path(client):
    skill = client.post(
        "/skills", json={"name": "AWS", "category": "cloud"}
    ).json()

    job = client.post(
        "/jobs", json={"company": "A", "title": "T", "role": "r"}
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    assert client.get("/today").json()["next_learning_step"] is None
