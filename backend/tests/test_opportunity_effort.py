"""Phase 3 — 필요 시간과 계획 연결.

남은 날짜만으로는 "할 수 있는가" 를 판단할 수 없다.
40시간짜리를 5일 안에 끝내는 것과 4시간짜리를 5일 안에 끝내는 것은 다르다.
"""

from datetime import datetime, timedelta

from app.services import opportunity as opportunity_service


def _in_days(days):
    return (datetime.now() + timedelta(days=days)).isoformat()


def _opportunity(client, **kw):
    payload = {
        "opportunity_type": "competition",
        "title": "AI 공모전",
        "source": "manual",
    }
    payload.update(kw)
    return client.post("/opportunities", json=payload).json()


def _skill(client, name="Python", level=2):
    return client.post(
        "/skills", json={"name": name, "category": "x", "level": level}
    ).json()


# --------------------------------
# 하루 몇 시간
# --------------------------------

def test_hours_per_day_needs_both_numbers():
    assert opportunity_service.hours_per_day(None, 10) is None
    assert opportunity_service.hours_per_day(40, None) is None


def test_hours_per_day_does_not_divide_by_zero():
    """오늘이 마감이어도 계산이 깨지지 않는다."""
    assert opportunity_service.hours_per_day(8, 0) == 8


def test_hours_per_day_math():
    assert opportunity_service.hours_per_day(40, 10) == 4


# --------------------------------
# 실현 가능성
# --------------------------------

def test_same_deadline_different_effort(client):
    """마감이 같아도 필요 시간이 다르면 판정이 달라야 한다."""
    skill = _skill(client)

    small = _opportunity(
        client, title="가벼운 것", deadline=_in_days(10), estimated_hours=5
    )
    huge = _opportunity(
        client, title="무거운 것", deadline=_in_days(10), estimated_hours=80
    )

    for o in (small, huge):
        client.post(f"/opportunities/{o['id']}/skills/{skill['id']}")

    small_match = client.get(f"/opportunities/{small['id']}/match").json()
    huge_match = client.get(f"/opportunities/{huge['id']}/match").json()

    assert small_match["deadline_state"] == "comfortable"
    assert huge_match["deadline_state"] == "unrealistic"
    assert small_match["match_score"] > huge_match["match_score"]


def test_unrealistic_effort_is_explained(client):
    skill = _skill(client)

    heavy = _opportunity(client, deadline=_in_days(5), estimated_hours=40)
    client.post(f"/opportunities/{heavy['id']}/skills/{skill['id']}")

    match = client.get(f"/opportunities/{heavy['id']}/match").json()
    text = " ".join(match["reasons"])

    assert match["hours_per_day"] == 8.0
    assert "하루 8.0시간" in text
    assert "끝내기 어렵습니다" in text


def test_without_effort_it_falls_back_to_days(client):
    """필요 시간을 모르면 예전처럼 남은 날짜로 판단한다."""
    skill = _skill(client)

    o = _opportunity(client, deadline=_in_days(2))
    client.post(f"/opportunities/{o['id']}/skills/{skill['id']}")

    match = client.get(f"/opportunities/{o['id']}/match").json()

    assert match["estimated_hours"] is None
    assert match["hours_per_day"] is None
    assert match["deadline_state"] == "tight"
    assert "촉박합니다" in " ".join(match["reasons"])


def test_effort_is_reported(client):
    o = _opportunity(client, deadline=_in_days(30), estimated_hours=12)

    match = client.get(f"/opportunities/{o['id']}/match").json()

    assert match["estimated_hours"] == 12
    assert match["hours_per_day"] == 0.4


# --------------------------------
# 계획에 추가 — DISCOVER 에서 Today 로
# --------------------------------

def test_adding_to_plan_creates_an_application_and_a_task(client):
    """기회만 계획에 넣고 지원서를 안 만들면 결과를 추적할 곳이 없다."""
    o = _opportunity(client, deadline=_in_days(20))

    body = client.post(f"/opportunities/{o['id']}/add-to-plan").json()

    assert body["created_application"] is True
    assert body["already_planned"] is False
    assert body["task"]["task_type"] == "application"
    assert "지원 준비" in body["task"]["title"]
    assert "마감까지 20일" in body["task"]["reason"]

    applications = client.get("/applications").json()
    assert len(applications) == 1
    assert applications[0]["status"] == "interested"
    assert applications[0]["opportunity_id"] == o["id"]

    plan = client.get("/today/plan").json()
    assert any("지원 준비" in t["title"] for t in plan["tasks"])


def test_adding_twice_does_not_duplicate(client):
    o = _opportunity(client)

    client.post(f"/opportunities/{o['id']}/add-to-plan")
    second = client.post(f"/opportunities/{o['id']}/add-to-plan").json()

    assert second["already_planned"] is True
    assert len(client.get("/applications").json()) == 1
    assert len(client.get("/today/plan").json()["tasks"]) == 1


def test_existing_application_is_reused(client):
    o = _opportunity(client)

    client.post(
        "/applications",
        json={"opportunity_id": o["id"], "status": "preparing"},
    )

    body = client.post(f"/opportunities/{o['id']}/add-to-plan").json()

    assert body["created_application"] is False
    assert len(client.get("/applications").json()) == 1
    # 사용자가 정한 상태를 덮어쓰지 않는다
    assert client.get("/applications").json()[0]["status"] == "preparing"


def test_planned_minutes_can_be_set(client):
    o = _opportunity(client)

    body = client.post(
        f"/opportunities/{o['id']}/add-to-plan?minutes=60"
    ).json()

    assert body["task"]["minutes"] == 60


def test_unknown_opportunity_returns_404(client):
    assert client.post("/opportunities/9999/add-to-plan").status_code == 404


def test_effort_can_be_set_by_patch(client):
    """Create 에만 넣고 Update 에 빠뜨리면 수정이 조용히 무시된다.

    Mission 022 에서 create_resource 가 importance 를 빠뜨린 것과 같은 유형.
    """
    o = _opportunity(client, deadline=_in_days(5))

    updated = client.patch(
        f"/opportunities/{o['id']}", json={"estimated_hours": 40}
    ).json()

    assert updated["estimated_hours"] == 40

    match = client.get(f"/opportunities/{o['id']}/match").json()
    assert match["hours_per_day"] == 8.0
    assert match["deadline_state"] == "unrealistic"


def test_plan_minutes_are_validated(client):
    """제약이 없으면 음수 분짜리 태스크가 계획에 들어간다.

    다른 시간 입력 엔드포인트에는 제약이 있는데 여기만 빠져 있었다.
    """
    o = _opportunity(client)

    for bad in (-5, 0, 4, 481, 999999):
        response = client.post(
            f"/opportunities/{o['id']}/add-to-plan?minutes={bad}"
        )
        assert response.status_code == 422, f"minutes={bad} 가 통과했다"

    assert client.get("/today/plan").json()["tasks"] == []

    ok = client.post(f"/opportunities/{o['id']}/add-to-plan?minutes=45")
    assert ok.status_code == 200
    assert ok.json()["task"]["minutes"] == 45
