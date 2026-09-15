"""증거 집계 — 홈 화면의 별 개수.

DESIGN.md 4c: 별은 장식이 아니라 실제로 쌓은 증거의 수다.
개수를 부풀리거나 0을 가리지 않는다.
"""

from app import models
from app.services import evidence as evidence_service


def _keys(body):
    return {item["key"]: item["count"] for item in body["breakdown"]}


# --------------------------------
# 빈 상태
# --------------------------------

def test_nothing_yet_means_zero(client):
    body = client.get("/analytics/evidence").json()

    assert body["total"] == 0
    assert body["is_empty"] is True
    assert all(item["count"] == 0 for item in body["breakdown"])


def test_breakdown_is_always_present(client):
    """총합만 주면 화면이 숫자의 근거를 설명할 수 없다."""
    body = client.get("/analytics/evidence").json()

    assert _keys(body).keys() == {
        "completed_learning_steps",
        "completed_projects",
        "experiences",
        "portfolio_entries",
        "rejected_applications",
    }

    for item in body["breakdown"]:
        assert item["label"]


# --------------------------------
# 학습 단계
# --------------------------------

def test_completed_learning_step_counts(client):
    skill = client.post(
        "/skills", json={"name": "AWS", "category": "cloud"}
    ).json()
    path = client.post(
        "/learning-paths", json={"title": "AWS", "skill_id": skill["id"]}
    ).json()

    step = client.post(
        "/learning-steps",
        json={"learning_path_id": path["id"], "title": "EC2", "position": 0},
    ).json()

    assert client.get("/analytics/evidence").json()["total"] == 0

    client.post(f"/learning-steps/{step['id']}/complete")

    body = client.get("/analytics/evidence").json()
    assert _keys(body)["completed_learning_steps"] == 1
    assert body["total"] == 1
    assert body["is_empty"] is False


def test_unfinished_step_is_not_evidence(client):
    skill = client.post(
        "/skills", json={"name": "AWS", "category": "cloud"}
    ).json()
    path = client.post(
        "/learning-paths", json={"title": "AWS", "skill_id": skill["id"]}
    ).json()
    step = client.post(
        "/learning-steps",
        json={"learning_path_id": path["id"], "title": "EC2", "position": 0},
    ).json()

    client.post(f"/learning-steps/{step['id']}/start")

    assert client.get("/analytics/evidence").json()["total"] == 0


# --------------------------------
# 프로젝트
# --------------------------------

def test_project_completed_by_status(client):
    client.post("/projects", json={"name": "A", "status": "completed"})

    body = client.get("/analytics/evidence").json()
    assert _keys(body)["completed_projects"] == 1


def test_project_completed_by_progress(client):
    """진행률만 100 으로 올리고 상태를 안 바꿔도 완료로 센다.

    실제로 끝낸 것을 안 세면 개수가 거짓이 된다.
    """
    client.post("/projects", json={"name": "A", "progress_percent": 100})

    body = client.get("/analytics/evidence").json()
    assert _keys(body)["completed_projects"] == 1


def test_project_is_counted_once_even_if_both_signals(client):
    client.post(
        "/projects",
        json={"name": "A", "status": "completed", "progress_percent": 100},
    )

    body = client.get("/analytics/evidence").json()
    assert _keys(body)["completed_projects"] == 1


def test_in_progress_project_is_not_evidence(client):
    client.post("/projects", json={"name": "A", "progress_percent": 70})

    assert client.get("/analytics/evidence").json()["total"] == 0


# --------------------------------
# 경험 / 포트폴리오
# --------------------------------

def test_experience_and_portfolio_count(client):
    experience = client.post(
        "/experiences",
        json={"experience_type": "project", "title": "Data Station"},
    ).json()

    client.post(f"/experiences/{experience['id']}/portfolio-entry")

    body = client.get("/analytics/evidence").json()
    counts = _keys(body)

    assert counts["experiences"] == 1
    assert counts["portfolio_entries"] == 1
    assert body["total"] == 2


# --------------------------------
# 떨어진 지원 — 인용문의 핵심
# --------------------------------

def test_rejected_application_becomes_a_star(client):
    """"Even if you miss" 를 화면에서 지키는 지점.

    불합격을 숨기면 이 은유가 거짓말이 된다.
    """
    opportunity = client.post(
        "/opportunities",
        json={"opportunity_type": "job", "title": "Intern", "source": "manual"},
    ).json()

    application = client.post(
        "/applications", json={"opportunity_id": opportunity["id"]}
    ).json()

    assert client.get("/analytics/evidence").json()["total"] == 0

    client.patch(f"/applications/{application['id']}", json={"status": "rejected"})

    body = client.get("/analytics/evidence").json()
    assert _keys(body)["rejected_applications"] == 1
    assert body["total"] == 1


def test_pending_application_is_not_evidence(client):
    """아직 결과가 안 나온 지원은 세지 않는다. 시도가 끝나야 별이다."""
    opportunity = client.post(
        "/opportunities",
        json={"opportunity_type": "job", "title": "Intern", "source": "manual"},
    ).json()
    client.post("/applications", json={"opportunity_id": opportunity["id"]})

    assert client.get("/analytics/evidence").json()["total"] == 0


# --------------------------------
# 합계
# --------------------------------

def test_total_is_the_sum_of_the_breakdown(client):
    client.post("/projects", json={"name": "A", "status": "completed"})
    client.post(
        "/experiences",
        json={"experience_type": "project", "title": "X"},
    )

    body = client.get("/analytics/evidence").json()

    assert body["total"] == sum(i["count"] for i in body["breakdown"])
    assert body["total"] == 2


def test_service_total_matches_the_endpoint(client, db_session):
    client.post("/projects", json={"name": "A", "status": "completed"})

    assert evidence_service.count_total(db_session) == (
        client.get("/analytics/evidence").json()["total"]
    )
