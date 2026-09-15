"""Mission 022 - 학습 완료가 우선순위까지 이어지는지 검증.

Mission 021 까지는 이 연쇄가 끊겨 있었다.
스텝을 아무리 완료해도 학습 우선순위와 Today Plan 이 그대로였다.
"""

from app.services import priority


# --------------------------------
# 가중치 계산 자체
# --------------------------------

def test_no_learning_path_keeps_mission021_behaviour():
    """학습 경로가 없으면 가중치가 1.0 이어서 기존 점수와 같다."""
    assert priority.calculate_learning_weight(0) == 1.0


def test_full_learning_gives_maximum_discount():
    expected = 1.0 - priority.MAX_LEARNING_EVIDENCE

    assert priority.calculate_learning_weight(100) == expected


def test_learning_evidence_stays_weaker_than_project_evidence():
    """학습만으로는 완료한 프로젝트 하나보다 강한 증거가 될 수 없다.

    프로젝트는 "만들어봤다" 이고 학습은 "배웠다" 이기 때문이다.
    """
    assert (
        priority.MAX_LEARNING_EVIDENCE
        < priority.PROJECT_EVIDENCE["completed"]
    )


def test_learning_weight_clamps_out_of_range_values():
    assert priority.calculate_learning_weight(-20) == 1.0
    assert priority.calculate_learning_weight(500) == 0.6


# --------------------------------
# 진행률 갱신 시점
# --------------------------------

def _make_path_with_steps(client, skill_id, step_count):
    path = client.post(
        "/learning-paths",
        json={"title": "AWS Path", "skill_id": skill_id},
    ).json()

    steps = [
        client.post(
            "/learning-steps",
            json={
                "learning_path_id": path["id"],
                "title": f"Step {i}",
                "position": i,
            },
        ).json()
        for i in range(step_count)
    ]

    return path, steps


def test_progress_updates_immediately_on_step_change(client):
    """진행률 조회 엔드포인트를 부르지 않아도 갱신되어야 한다.

    Mission 021 에서는 GET /progress 가 저장까지 했기 때문에
    그걸 부르기 전에는 경로 진행률이 낡은 값이었다.
    """
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud"},
    ).json()

    path, steps = _make_path_with_steps(client, skill["id"], 4)

    client.patch(
        f"/learning-steps/{steps[0]['id']}",
        json={"status": "completed"},
    )

    # GET /progress 를 거치지 않고 경로를 바로 조회한다
    stored = client.get(f"/learning-paths/{path['id']}").json()

    assert stored["progress_percent"] == 25
    assert stored["status"] == "in_progress"


def test_progress_endpoint_is_read_only(client):
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud"},
    ).json()

    path, steps = _make_path_with_steps(client, skill["id"], 2)

    client.patch(
        f"/learning-steps/{steps[0]['id']}",
        json={"status": "completed"},
    )

    before = client.get(f"/learning-paths/{path['id']}").json()
    client.get(f"/learning-paths/{path['id']}/progress")
    after = client.get(f"/learning-paths/{path['id']}").json()

    assert before == after


def test_deleting_a_step_recalculates_progress(client):
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud"},
    ).json()

    path, steps = _make_path_with_steps(client, skill["id"], 2)

    client.patch(
        f"/learning-steps/{steps[0]['id']}",
        json={"status": "completed"},
    )
    assert client.get(
        f"/learning-paths/{path['id']}"
    ).json()["progress_percent"] == 50

    # 미완료 스텝을 지우면 남은 스텝이 전부 완료 상태가 된다
    client.delete(f"/learning-steps/{steps[1]['id']}")

    stored = client.get(f"/learning-paths/{path['id']}").json()

    assert stored["progress_percent"] == 100
    assert stored["status"] == "completed"


# --------------------------------
# 연쇄: 학습 -> 우선순위
# --------------------------------

def _skill_with_demand(client, name, level=0):
    skill = client.post(
        "/skills",
        json={"name": name, "category": "x", "level": level},
    ).json()

    return skill


def test_learning_progress_lowers_priority_score(client):
    skill = _skill_with_demand(client, "AWS")

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    before = client.get("/analytics/learning-priority").json()
    before_item = before["learning_priority"][0]

    assert before_item["priority_score"] == 400
    assert before_item["learning_progress"] == 0

    path, steps = _make_path_with_steps(client, skill["id"], 2)

    for step in steps:
        client.patch(
            f"/learning-steps/{step['id']}",
            json={"status": "completed"},
        )

    after_item = client.get(
        "/analytics/learning-priority"
    ).json()["learning_priority"][0]

    assert after_item["learning_progress"] == 100
    assert after_item["has_learning_evidence"] is True
    assert after_item["learning_weight"] == 0.6
    assert after_item["priority_score"] == 240
    assert after_item["priority_score"] < before_item["priority_score"]


def test_project_and_learning_evidence_combine(client):
    skill = _skill_with_demand(client, "AWS")

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    project = client.post(
        "/projects",
        json={
            "name": "AWS Deployment",
            "status": "completed",
            "progress_percent": 100,
        },
    ).json()
    client.post(f"/projects/{project['id']}/skills/{skill['id']}")

    path, steps = _make_path_with_steps(client, skill["id"], 1)
    client.patch(
        f"/learning-steps/{steps[0]['id']}",
        json={"status": "completed"},
    )

    item = client.get(
        "/analytics/learning-priority"
    ).json()["learning_priority"][0]

    # 만든 것(0.50)과 배운 것(0.40)이 겹치는 만큼을 빼고 합쳐진다.
    assert item["project_strength"] == 0.5
    assert item["learning_strength"] == 0.4
    assert item["evidence_strength"] == 0.7

    assert item["evidence_weight"] == 0.3
    assert item["priority_score"] == 120


def test_agent_sees_the_same_updated_score(client):
    """Agent 와 API 가 계속 같은 값을 봐야 한다."""
    skill = _skill_with_demand(client, "AWS")

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    path, steps = _make_path_with_steps(client, skill["id"], 1)
    client.patch(
        f"/learning-steps/{steps[0]['id']}",
        json={"status": "completed"},
    )

    from_api = client.get(
        "/analytics/learning-priority"
    ).json()["learning_priority"]

    from_agent = client.post(
        "/agent",
        json={"message": "지금 뭐 공부해야 해?"},
    ).json()["result"]

    assert [item["priority_score"] for item in from_api] == [
        item["priority_score"] for item in from_agent
    ]


# --------------------------------
# 연쇄: 학습 -> Today Plan
# --------------------------------

def test_learning_changes_todays_focus_skill(client):
    """루프가 실제로 닫혔다는 증거.

    수요와 레벨이 같은 두 스킬 중 하나를 학습하면
    다음 Today Plan 의 집중 스킬이 다른 쪽으로 넘어가야 한다.
    """
    aws = _skill_with_demand(client, "AWS")
    sql = _skill_with_demand(client, "SQL")

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{aws['id']}")
    client.post(f"/jobs/{job['id']}/skills/{sql['id']}")

    # 동점 상태에서는 먼저 만들어진 AWS 가 잡힌다
    assert client.get("/today").json()["focus_skill"] == "AWS"

    path, steps = _make_path_with_steps(client, aws["id"], 2)

    for step in steps:
        client.patch(
            f"/learning-steps/{step['id']}",
            json={"status": "completed"},
        )

    # AWS 를 학습했으니 이제 SQL 이 더 급하다
    assert client.get("/today").json()["focus_skill"] == "SQL"


def test_weekly_plan_reflects_learning_progress(client):
    aws = _skill_with_demand(client, "AWS")
    sql = _skill_with_demand(client, "SQL")

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{aws['id']}")
    client.post(f"/jobs/{job['id']}/skills/{sql['id']}")

    for skill_id, title in ((aws["id"], "AWS 자료"), (sql["id"], "SQL 자료")):
        client.post(
            "/resources",
            json={
                "title": title,
                "url": f"https://example.com/{skill_id}",
                "duration_minutes": 30,
                "skill_id": skill_id,
            },
        )

    path, steps = _make_path_with_steps(client, aws["id"], 1)
    client.patch(
        f"/learning-steps/{steps[0]['id']}",
        json={"status": "completed"},
    )

    body = client.get("/weekly-plan?daily_available_minutes=30").json()

    first_resource = next(
        task
        for day in body["weekly_plan"]
        for task in day["tasks"]
        if task["type"] == "resource"
    )

    assert first_resource["skill"] == "SQL"
