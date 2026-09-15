"""Mission 023 - 자동화 파이프라인이 Opportunity 로 옮겨간 뒤에도
기존 대시보드가 깨지지 않는지 확인한다."""


def test_pipeline_collects_scores_and_snapshots(client):
    client.post("/skills", json={"name": "Python", "category": "lang"})

    body = client.post("/automation/run").json()

    assert body["status"] == "completed"
    assert body["opportunities"]["fetched"] == 2
    assert body["opportunities"]["created"] == 2
    assert body["opportunities"]["scored"] == 2
    assert body["market"]["snapshot_rows"] == 1
    assert body["market"]["total_opportunities"] == 2


def test_pipeline_keeps_the_keys_the_dashboard_reads(client):
    """App.jsx 가 collector.fetched_count 등을 직접 읽는다."""
    body = client.post("/automation/run").json()

    collector = body["collector"]
    assert "fetched_count" in collector
    assert "created_count" in collector
    assert "skipped_count" in collector

    state = body["career_state"]
    for key in (
        "jobs_count",
        "projects_count",
        "resources_count",
        "learning_priority",
    ):
        assert key in state


def test_pipeline_is_idempotent(client):
    client.post("/automation/run")
    second = client.post("/automation/run").json()

    assert second["opportunities"]["created"] == 0
    assert second["opportunities"]["updated"] == 2
    assert len(client.get("/opportunities").json()) == 2


def test_pipeline_populates_legacy_jobs_for_the_dashboard(client):
    client.post("/automation/run")

    jobs = client.get("/jobs").json()

    assert len(jobs) == 1
    assert jobs[0]["title"] == "Data Scientist Intern"


def test_pipeline_only_surfaces_what_is_worth_doing(client):
    client.post("/skills", json={"name": "Python", "category": "lang"})

    body = client.post("/automation/run").json()

    assert body["opportunities"]["worth_doing"] <= body["opportunities"]["scored"]
    assert len(body["opportunities"]["top"]) <= 3

    for match in body["opportunities"]["top"]:
        assert match["recommendation"] in ("recommended", "consider")
        assert match["reasons"]


def test_agent_can_still_run_automation(client):
    body = client.post("/agent", json={"message": "전체 업데이트 해줘"}).json()

    assert body["intent"] == "automation"
    assert body["result"]["status"] == "completed"


def test_dashboard_endpoints_still_work_after_the_pipeline(client):
    client.post("/skills", json={"name": "Python", "category": "lang"})
    client.post("/automation/run")

    assert client.get("/today").status_code == 200
    assert client.get("/weekly-plan").status_code == 200
    assert client.get("/analytics/learning-priority").status_code == 200
    assert client.get("/analytics/skills").status_code == 200
    assert client.get("/projects").status_code == 200
