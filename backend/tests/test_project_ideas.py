"""하고자 하는 프로젝트 — 기획안을 넣어두는 자리.

언제 할지 모르지만 하고 싶은 것을 적어둔다. 계획에는 올라오지 않는다 —
적어두는 것이 부담이 되면 아무것도 안 적게 된다.
why 는 "왜 하려는가" 다. 공고에 쓸지 판단하는 근거가 된다.
"""


def _idea(client, name="Past vs Now 확장", why="장기 취향과 현재 의도의 경계를 실험으로 확인하고 싶다"):
    return client.post("/projects", json={
        "name": name,
        "status": "idea",
        "why": why,
        "description": "Kindle_Store 로 RQ3 를 먼저 좁게 확인한다",
    }).json()


def test_an_idea_keeps_why(client):
    made = _idea(client)

    assert made["status"] == "idea"
    assert "장기 취향" in made["why"]


def test_an_idea_does_not_reach_todays_plan(client):
    _idea(client)

    plan = client.post("/today/plan?available_minutes=180&intensity=normal").json()

    assert [t for t in plan["tasks"] if t["task_type"] == "project"] == []


def test_a_started_idea_reaches_the_plan(client):
    made = _idea(client)

    client.patch(f"/projects/{made['id']}", json={"status": "in_progress"})
    plan = client.post("/today/plan?available_minutes=180&intensity=normal").json()

    titles = [t["title"] for t in plan["tasks"] if t["task_type"] == "project"]
    assert titles == ["Past vs Now 확장"]


def test_why_can_be_written_later(client):
    made = client.post("/projects", json={"name": "무제 기획", "status": "idea"}).json()
    assert made["why"] == ""

    saved = client.patch(f"/projects/{made['id']}", json={
        "why": "추천시스템 수업에서 배운 것을 내 데이터로 다시 확인하려고",
    }).json()

    assert "내 데이터로" in saved["why"]
