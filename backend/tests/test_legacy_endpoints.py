"""기존 MVP 엔드포인트 회귀 테스트.

Mission 021 리팩터링(우선순위 통합, create_all 제거, 라우터 도입)이
기존 동작을 깨지 않았는지 확인한다.
"""

import pytest

from app import main


def test_root(client):
    """화면이 없을 때만 "/" 가 API 인사말이다.

    화면을 빌드해서 backend/static 에 두면 "/" 는 그 화면이 가진다
    (main.py 의 HAS_FRONTEND). 그게 배포본의 정상 동작이므로,
    화면을 한 번 빌드해본 사람이 이 테스트로 막히면 안 된다.
    """
    if main.HAS_FRONTEND:
        pytest.skip("backend/static 이 있으면 '/' 는 화면이 가진다")

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Career OS API is running"}


def test_skill_and_project_crud_still_work(client):
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 1},
    )
    assert skill.status_code == 200

    project = client.post(
        "/projects",
        json={"name": "AWS Deployment", "estimated_hours": 10},
    )
    assert project.status_code == 200

    link = client.post(
        f"/projects/{project.json()['id']}/skills/{skill.json()['id']}"
    )
    assert link.status_code == 200

    linked = client.get(f"/projects/{project.json()['id']}/skills")
    assert [s["name"] for s in linked.json()] == ["AWS"]


def test_learning_priority_response_shape(client):
    """프런트엔드가 읽는 키가 그대로 남아있는지."""
    skill = client.post(
        "/skills",
        json={"name": "SQL", "category": "data", "level": 1},
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()

    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    body = client.get("/analytics/learning-priority").json()

    assert body["total_demand"] == 1

    item = body["learning_priority"][0]

    # App.jsx 가 직접 읽는 키들
    for key in ("skill", "my_level", "market_percentage", "priority_score"):
        assert key in item

    assert item["skill"] == "SQL"
    assert item["priority_score"] == 300
    assert item["resources"] == []


def test_today_plan(client):
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
        "/resources",
        json={
            "title": "EC2 Basics",
            "url": "https://example.com/ec2",
            "duration_minutes": 30,
            "skill_id": skill["id"],
        },
    )

    body = client.get("/today").json()

    assert body["focus_skill"] == "AWS"
    assert body["priority_score"] == 400
    assert body["recommended_resource"]["title"] == "EC2 Basics"
    # 한국어 앱이다. 문구를 옮기면서 이 줄도 같이 옮겼다.
    assert body["today_action"] == "EC2 Basics — 30분"


def test_today_plan_with_no_skills(client):
    assert client.get("/today").json() == {"message": "No skills available."}


def test_weekly_plan(client):
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
        "/resources",
        json={
            "title": "EC2 Basics",
            "url": "https://example.com/ec2",
            "duration_minutes": 30,
            "skill_id": skill["id"],
        },
    )

    body = client.get("/weekly-plan?daily_available_minutes=60").json()

    assert body["daily_available_minutes"] == 60
    assert len(body["weekly_plan"]) == 7
    assert body["weekly_plan"][0]["day"] == "Monday"

    # 같은 리소스가 일주일 내내 반복되면 안 된다
    used = [
        task["resource_id"]
        for day in body["weekly_plan"]
        for task in day["tasks"]
        if task["type"] == "resource"
    ]
    assert len(used) == len(set(used))


def test_job_match(client):
    skill = client.post(
        "/skills",
        json={"name": "Python", "category": "lang", "level": 2},
    ).json()

    gap = client.post(
        "/skills",
        json={"name": "Docker", "category": "infra", "level": 0},
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()

    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")
    client.post(f"/jobs/{job['id']}/skills/{gap['id']}")

    body = client.get(f"/jobs/{job['id']}/match").json()

    assert body["match_score"] == 50
    assert body["matched_skills"] == ["Python"]
    assert body["missing_skills"] == ["Docker"]


def test_project_eta(client):
    project = client.post(
        "/projects",
        json={
            "name": "P",
            "estimated_hours": 10,
            "progress_percent": 50,
            "daily_minutes": 60,
        },
    ).json()

    body = client.get(f"/projects/{project['id']}/eta").json()

    assert body["remaining_hours"] == 5.0
    assert body["days_needed"] == 5


def test_agent_today_intent(client):
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()

    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    body = client.post("/agent", json={"message": "오늘 60분밖에 없어"}).json()

    assert body["intent"] == "today"
    assert body["result"]["focus_skill"] == "AWS"
    assert body["result"]["available_minutes"] == 60


def test_today_reason_carries_the_denominator(client):
    """퍼센트만 보내면 화면이 거짓말을 하게 된다.

    공고가 1건뿐인데 "100%" 라고 쓰면 시장 전체가 요구하는 것처럼
    읽힌다. 분모를 같이 보내서 "1건 중 1건" 으로 쓸 수 있게 한다.
    """
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    ).json()

    wanted = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{wanted['id']}/skills/{skill['id']}")

    # AWS 를 요구하지 않는 공고도 하나 둔다 — 분모가 2가 되어야 한다.
    client.post(
        "/jobs",
        json={"company": "B", "title": "T2", "role": "r"},
    )

    reason = client.get("/today").json()["reason"]

    assert reason["demand_count"] == 1
    assert reason["total_demand"] == 2
    assert reason["market_percentage"] == 50


def test_today_reason_names_the_project_evidence(client):
    """"증거 있음" 이 아니라 무엇이 증거인지 말한다."""
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    project = client.post(
        "/projects",
        json={
            "name": "AWS Deployment Project",
            "career_related": True,
        },
    ).json()
    client.post(f"/projects/{project['id']}/skills/{skill['id']}")

    reason = client.get("/today").json()["reason"]

    assert reason["has_project_evidence"] is True
    assert reason["career_projects"] == ["AWS Deployment Project"]


def test_today_reason_is_empty_when_there_is_no_evidence(client):
    """근거가 없으면 빈 목록을 보낸다. 지어내지 않는다."""
    client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    )

    reason = client.get("/today").json()["reason"]

    assert reason["total_demand"] == 0
    assert reason["demand_count"] == 0
    assert reason["career_projects"] == []
