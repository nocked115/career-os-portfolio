"""Target Career — 모든 우선순위 계산의 기준점 (Phase 1)."""

from app.services import priority as priority_service


def _make(client, title="Data Scientist", **kw):
    payload = {"title": title}
    payload.update(kw)
    return client.post("/target-careers", json=payload).json()


def _skill(client, name, level=0):
    return client.post(
        "/skills", json={"name": name, "category": "x", "level": level}
    ).json()


def _job_with(client, skills):
    job = client.post(
        "/jobs", json={"company": "A", "title": "T", "role": "r"}
    ).json()
    for s in skills:
        client.post(f"/jobs/{job['id']}/skills/{s['id']}")
    return job


def _by_skill(client):
    body = client.get("/analytics/learning-priority").json()
    return {i["skill"]: i for i in body["learning_priority"]}


# --------------------------------
# 기본 동작
# --------------------------------

def test_no_target_career_is_a_normal_state(client):
    """정하지 않은 것은 오류가 아니다."""
    body = client.get("/target-careers/active").json()

    assert body["target_career"] is None
    assert "아직 없습니다" in body["message"]


def test_create_and_activate(client):
    target = _make(client, "Data Scientist", keywords="data, ml, python")

    assert target["is_active"] is False

    client.post(f"/target-careers/{target['id']}/activate")

    body = client.get("/target-careers/active").json()

    assert body["target_career"]["title"] == "Data Scientist"
    assert body["target_career"]["keywords"] == ["data", "ml", "python"]


def test_creating_as_active_works(client):
    _make(client, "Data Scientist", is_active=True)

    body = client.get("/target-careers/active").json()
    assert body["target_career"]["title"] == "Data Scientist"


def test_only_one_can_be_active(client):
    first = _make(client, "Data Scientist", is_active=True)
    second = _make(client, "Backend Engineer", is_active=True)

    listed = client.get("/target-careers").json()
    active = [t for t in listed if t["is_active"]]

    assert len(active) == 1
    assert active[0]["id"] == second["id"]

    client.post(f"/target-careers/{first['id']}/activate")

    listed = client.get("/target-careers").json()
    active = [t for t in listed if t["is_active"]]
    assert len(active) == 1
    assert active[0]["id"] == first["id"]


def test_switching_keeps_the_old_target(client):
    """목표를 바꿔도 이전 것을 지우지 않는다."""
    _make(client, "Data Scientist", is_active=True)
    _make(client, "Backend Engineer", is_active=True)

    assert len(client.get("/target-careers").json()) == 2


def test_static_route_is_not_swallowed_by_the_id_route(client):
    assert client.get("/target-careers/active").status_code == 200


def test_unknown_target_returns_404(client):
    assert client.get("/target-careers/9999").status_code == 404
    assert client.post("/target-careers/9999/activate").status_code == 404


# --------------------------------
# 스킬 연결
# --------------------------------

def test_link_and_unlink_skills(client):
    target = _make(client)
    python = _skill(client, "Python")

    client.post(f"/target-careers/{target['id']}/skills/{python['id']}")

    names = [
        s["name"]
        for s in client.get(f"/target-careers/{target['id']}/skills").json()
    ]
    assert names == ["Python"]

    client.delete(f"/target-careers/{target['id']}/skills/{python['id']}")
    assert client.get(f"/target-careers/{target['id']}/skills").json() == []


# --------------------------------
# 우선순위에 미치는 영향 — 핵심
# --------------------------------

def test_without_target_all_skills_weigh_the_same(client):
    """목표가 없으면 이전과 결과가 같아야 한다 (하위 호환)."""
    python = _skill(client, "Python")
    rust = _skill(client, "Rust")
    _job_with(client, [python, rust])

    items = _by_skill(client)

    assert items["Python"]["target_weight"] == 1.0
    assert items["Rust"]["target_weight"] == 1.0
    assert items["Python"]["target_relevant"] is None
    assert items["Python"]["priority_score"] == items["Rust"]["priority_score"]


def test_target_skills_outrank_unrelated_ones(client):
    """수요가 같아도 목표와 관련된 쪽이 먼저다."""
    python = _skill(client, "Python")
    rust = _skill(client, "Rust")
    _job_with(client, [python, rust])

    target = _make(client, "Data Scientist", is_active=True)
    client.post(f"/target-careers/{target['id']}/skills/{python['id']}")

    items = _by_skill(client)

    assert items["Python"]["target_relevant"] is True
    assert items["Rust"]["target_relevant"] is False
    assert items["Python"]["target_weight"] == 1.0
    assert items["Rust"]["target_weight"] == 0.6

    assert items["Python"]["priority_score"] > items["Rust"]["priority_score"]
    assert items["Rust"]["priority_score"] == round(
        items["Python"]["priority_score"] * 0.6
    )


def test_unrelated_skill_is_lowered_not_removed(client):
    """목표와 무관해도 0 으로 만들지 않는다. 목표는 바뀔 수 있다."""
    rust = _skill(client, "Rust")
    _job_with(client, [rust])

    target = _make(client, "Data Scientist", is_active=True)

    items = _by_skill(client)
    assert items["Rust"]["priority_score"] > 0


def test_target_career_name_is_reported(client):
    python = _skill(client, "Python")
    _job_with(client, [python])

    target = _make(client, "Data Scientist", is_active=True)
    client.post(f"/target-careers/{target['id']}/skills/{python['id']}")

    assert _by_skill(client)["Python"]["target_career"] == "Data Scientist"


def test_deactivating_restores_neutral_weights(client):
    python = _skill(client, "Python")
    rust = _skill(client, "Rust")
    _job_with(client, [python, rust])

    target = _make(client, "Data Scientist", is_active=True)
    client.post(f"/target-careers/{target['id']}/skills/{python['id']}")

    assert _by_skill(client)["Rust"]["target_weight"] == 0.6

    client.delete(f"/target-careers/{target['id']}")

    items = _by_skill(client)
    assert items["Rust"]["target_weight"] == 1.0
    assert items["Python"]["priority_score"] == items["Rust"]["priority_score"]


def test_today_focus_follows_the_target(client):
    """목표를 정하면 오늘의 집중 스킬이 바뀐다."""
    python = _skill(client, "Python")
    rust = _skill(client, "Rust")
    _job_with(client, [python, rust])

    # 동점 상태에서는 먼저 만든 Python 이 잡힌다
    assert client.get("/today").json()["focus_skill"] == "Python"

    target = _make(client, "Systems Engineer", is_active=True)
    client.post(f"/target-careers/{target['id']}/skills/{rust['id']}")

    assert client.get("/today").json()["focus_skill"] == "Rust"


def test_agent_sees_the_same_target_weighted_scores(client):
    python = _skill(client, "Python")
    _job_with(client, [python])

    target = _make(client, "Data Scientist", is_active=True)
    client.post(f"/target-careers/{target['id']}/skills/{python['id']}")

    from_api = client.get(
        "/analytics/learning-priority"
    ).json()["learning_priority"]
    from_agent = client.post(
        "/agent", json={"message": "지금 뭐 공부해야 해?"}
    ).json()["result"]

    assert [i["priority_score"] for i in from_api] == [
        i["priority_score"] for i in from_agent
    ]


def test_opportunity_matching_inherits_the_target(client):
    """기회 매칭은 우선순위를 통해 목표를 물려받는다.

    별도 계산 지점을 만들지 않았기 때문에 자동으로 반영된다.
    """
    python = _skill(client, "Python")
    rust = _skill(client, "Rust")

    on_target = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "Data role",
            "source": "manual",
            "description": "Python required.",
        },
    ).json()
    off_target = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "Systems role",
            "source": "manual",
            "description": "Rust required.",
        },
    ).json()

    # 수동 생성한 기회는 스킬이 자동 연결되지 않는다 (수집 경로만 연결한다).
    client.post(f"/opportunities/{on_target['id']}/skills/{python['id']}")
    client.post(f"/opportunities/{off_target['id']}/skills/{rust['id']}")

    _job_with(client, [python, rust])

    target = _make(client, "Data Scientist", is_active=True)
    client.post(f"/target-careers/{target['id']}/skills/{python['id']}")

    on_score = client.get(
        f"/opportunities/{on_target['id']}/match"
    ).json()["breakdown"]["relevance"]
    off_score = client.get(
        f"/opportunities/{off_target['id']}/match"
    ).json()["breakdown"]["relevance"]

    assert on_score > off_score


# --------------------------------
# 서비스 단위
# --------------------------------

def test_weight_helper_is_neutral_without_a_target():
    class FakeSkill:
        id = 1

    assert priority_service.calculate_target_weight(FakeSkill(), set()) == 1.0
