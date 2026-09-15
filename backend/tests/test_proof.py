"""PROVE — 활동을 증거로 바꾸는 흐름 (Phase 4).

프로젝트를 끝내도 아무 제안이 없으면 사용자는 그냥 잊는다.
증거화는 자동 제안이 있어야 실제로 일어난다.

근거 규칙: 저장된 내용에서만 만든다. 없는 성과를 지어내지 않는다.
"""

from app.services import proof as proof_service


def _project(client, **kw):
    payload = {"name": "AWS Deployment"}
    payload.update(kw)
    return client.post("/projects", json=payload).json()


def _skill(client, name):
    return client.post(
        "/skills", json={"name": name, "category": "x"}
    ).json()


def _done_project(client, **kw):
    project = _project(client, status="completed", **kw)
    return project


# --------------------------------
# 제안
# --------------------------------

def test_unfinished_project_says_not_yet(client):
    """완료 안 됐다는 것도 정확한 상태다."""
    project = _project(client, progress_percent=70)

    body = client.get(f"/projects/{project['id']}/evidence").json()

    assert body["is_complete"] is False
    assert "완료하면" in body["message"]


def test_progress_100_counts_as_complete(client):
    """진행률만 올리고 상태를 안 바꾼 경우도 완료로 본다."""
    project = _project(client, progress_percent=100)

    assert client.get(
        f"/projects/{project['id']}/evidence"
    ).json()["is_complete"] is True


def test_completed_project_lists_what_it_proves(client):
    project = _done_project(client)

    for name in ("AWS", "FastAPI", "Docker"):
        skill = _skill(client, name)
        client.post(f"/projects/{project['id']}/skills/{skill['id']}")

    body = client.get(f"/projects/{project['id']}/evidence").json()

    assert body["proves"] == ["AWS", "FastAPI", "Docker"]
    assert "AWS · FastAPI · Docker" in body["message"]


def test_completed_without_skills_says_so(client):
    """무엇을 증명하는지 모르면 모른다고 말한다."""
    project = _done_project(client)

    body = client.get(f"/projects/{project['id']}/evidence").json()

    assert body["proves"] == []
    assert "무엇을 증명하는지 알 수 없습니다" in body["message"]


def test_every_action_has_a_reason(client):
    project = _done_project(client)

    body = client.get(f"/projects/{project['id']}/evidence").json()

    keys = [a["key"] for a in body["actions"]]
    assert keys == [
        "record_results",
        "add_github_url",
        "add_demo_url",
        "save_to_experience",
        "prepare_portfolio",
        "generate_resume_bullet",
    ]

    for action in body["actions"]:
        assert action["hint"]
        assert action["done"] is False


def test_filling_a_field_marks_the_action_done(client):
    project = _done_project(client)

    client.patch(
        f"/projects/{project['id']}",
        json={"github_url": "https://github.com/me/aws", "results": "배포 자동화"},
    )

    body = client.get(f"/projects/{project['id']}/evidence").json()
    done = {a["key"]: a["done"] for a in body["actions"]}

    assert done["add_github_url"] is True
    assert done["record_results"] is True
    assert done["add_demo_url"] is False
    assert body["remaining_count"] == 4


# --------------------------------
# 프로젝트 수정 — Phase 4 이전에는 수단이 없었다
# --------------------------------

def test_project_can_be_updated(client):
    project = _project(client)

    updated = client.patch(
        f"/projects/{project['id']}",
        json={"progress_percent": 100, "demo_url": "https://demo.example"},
    ).json()

    assert updated["progress_percent"] == 100
    assert updated["demo_url"] == "https://demo.example"
    # 안 보낸 필드는 그대로
    assert updated["name"] == "AWS Deployment"


# --------------------------------
# Experience 로 전환
# --------------------------------

def test_project_becomes_an_experience(client):
    project = _done_project(
        client, description="배포 자동화", results="배포 시간 단축"
    )

    aws = _skill(client, "AWS")
    client.post(f"/projects/{project['id']}/skills/{aws['id']}")

    experience = client.post(
        f"/projects/{project['id']}/to-experience"
    ).json()

    assert experience["title"] == "AWS Deployment"
    assert experience["experience_type"] == "project"
    assert experience["results"] == "배포 시간 단축"
    assert experience["technologies"] == "AWS"
    assert experience["project_id"] == project["id"]

    skills = client.get(f"/experiences/{experience['id']}/skills").json()
    assert [s["name"] for s in skills] == ["AWS"]


def test_converting_twice_reuses_the_same_experience(client):
    project = _done_project(client)

    first = client.post(f"/projects/{project['id']}/to-experience").json()
    second = client.post(f"/projects/{project['id']}/to-experience").json()

    assert first["id"] == second["id"]
    assert len(client.get("/experiences").json()) == 1


def test_suggestions_track_the_conversion(client):
    project = _done_project(client)

    experience = client.post(
        f"/projects/{project['id']}/to-experience"
    ).json()
    client.post(f"/experiences/{experience['id']}/portfolio-entry")

    body = client.get(f"/projects/{project['id']}/evidence").json()
    done = {a["key"]: a["done"] for a in body["actions"]}

    assert done["save_to_experience"] is True
    assert done["prepare_portfolio"] is True
    assert body["experience_id"] == experience["id"]
    assert body["portfolio_entry_id"] is not None


# --------------------------------
# 이력서 문장 — 지어내지 않는다
# --------------------------------

def _portfolio(client, **kw):
    payload = {"title": "AWS Deployment"}
    payload.update(kw)
    return client.post("/portfolio-entries", json=payload).json()


def test_empty_entry_refuses_to_invent(client):
    """무엇을 했고 어떤 결과가 있었는지 없으면 문장을 만들지 않는다."""
    entry = _portfolio(client)

    body = client.post(
        f"/portfolio-entries/{entry['id']}/resume-bullet"
    ).json()

    assert body["draft"] is None
    assert body["saved"] is False
    assert "지어내지 않습니다" in body["message"]


def test_bullet_is_assembled_from_stored_fields(client):
    entry = _portfolio(
        client,
        technologies="AWS, FastAPI",
        actions="배포 파이프라인 구성",
        results="배포 시간 30분 → 5분",
    )

    body = client.post(
        f"/portfolio-entries/{entry['id']}/resume-bullet"
    ).json()

    assert body["saved"] is True
    assert "AWS, FastAPI 기반" in body["draft"]
    assert "배포 파이프라인 구성" in body["draft"]
    assert "배포 시간 30분 → 5분" in body["draft"]
    assert body["missing"] == []

    stored = client.get(f"/portfolio-entries/{entry['id']}").json()
    assert stored["resume_bullet"] == body["draft"]


def test_partial_material_still_drafts_but_reports_gaps(client):
    entry = _portfolio(client, actions="배포 파이프라인 구성")

    body = client.post(
        f"/portfolio-entries/{entry['id']}/resume-bullet"
    ).json()

    assert body["draft"] is not None
    assert "results" in body["missing"]
    assert "technologies" in body["missing"]
    assert "비어 있는 항목이 있어" in body["message"]


def test_role_can_stand_in_for_actions(client):
    entry = _portfolio(client, role="배포 담당", results="자동화 완료")

    body = client.post(
        f"/portfolio-entries/{entry['id']}/resume-bullet"
    ).json()

    assert "배포 담당" in body["draft"]


def test_bullet_uses_only_the_first_line(client):
    entry = _portfolio(
        client,
        actions="- 첫 줄\n- 둘째 줄\n- 셋째 줄",
        results="성공",
    )

    body = client.post(
        f"/portfolio-entries/{entry['id']}/resume-bullet"
    ).json()

    assert "첫 줄" in body["draft"]
    assert "둘째 줄" not in body["draft"]


# --------------------------------
# 서비스 단위
# --------------------------------

def test_first_line_strips_bullet_markers():
    assert proof_service._first_line("- 첫 줄\n둘째") == "첫 줄"
    assert proof_service._first_line("\n\n  · 값  \n") == "값"
    assert proof_service._first_line("") == ""


def test_unknown_project_returns_404(client):
    assert client.get("/projects/9999/evidence").status_code == 404
    assert client.post("/projects/9999/to-experience").status_code == 404


# --------------------------------
# 회귀 방지 — 같은 버그가 세 번 났다
# --------------------------------

def test_create_endpoints_do_not_drop_new_fields(client):
    """스키마의 모든 필드가 실제로 저장되어야 한다.

    필드를 하나씩 나열하는 방식 때문에 세 번 같은 버그가 났다.
    importance(Mission 022) · estimated_hours(Phase 3) · results(Phase 4).
    """
    project = client.post(
        "/projects",
        json={
            "name": "P",
            "description": "d",
            "status": "completed",
            "career_related": False,
            "estimated_hours": 12,
            "progress_percent": 100,
            "daily_minutes": 45,
            "target_date": "2026-12-31",
            "github_url": "https://github.com/me/p",
            "demo_url": "https://demo.example",
            "results": "완료",
        },
    ).json()

    for key, expected in [
        ("description", "d"),
        ("status", "completed"),
        ("career_related", False),
        ("estimated_hours", 12),
        ("progress_percent", 100),
        ("daily_minutes", 45),
        ("target_date", "2026-12-31"),
        ("github_url", "https://github.com/me/p"),
        ("demo_url", "https://demo.example"),
        ("results", "완료"),
    ]:
        assert project[key] == expected, f"{key} 가 저장되지 않았다"


def test_skill_and_job_create_keep_every_field(client):
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 3,
              "status": "in_progress"},
    ).json()

    assert skill["level"] == 3
    assert skill["status"] == "in_progress"

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r",
              "employment_type": "fulltime", "url": "https://x",
              "deadline": "2026-12-31", "description": "d",
              "status": "interested"},
    ).json()

    assert job["employment_type"] == "fulltime"
    assert job["deadline"] == "2026-12-31"
    assert job["status"] == "interested"


def test_added_text_columns_are_never_null(client, db_session):
    """ALTER 로 추가한 텍스트 컬럼에 server_default 를 빠뜨리면
    기존 행이 NULL 이 되고 응답 직렬화가 500 으로 죽는다.

    Phase 2 의 unit_label, Phase 4 의 results 에서 실제로 났다.
    """
    from app import models, schemas

    project = models.Project(name="직접 만든 것")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # ORM 기본값을 거치지 않고 DB 가 채운 값이어야 한다
    assert project.results is not None
    assert project.github_url is not None
    assert project.demo_url is not None

    schemas.ProjectResponse.model_validate(project)

    assert client.get("/projects").status_code == 200


def test_project_response_carries_its_skills(client):
    """프로젝트가 무엇으로 만들어졌는지가 곧 그 프로젝트가 증명하는 것이다.

    응답에서 빠지면 화면이 기술 태그를 그릴 수 없다.
    이 저장소에서 응답 필드 누락은 반복된 함정이라 테스트로 막는다.
    """
    skill = client.post(
        "/skills", json={"name": "AWS", "category": "cloud"}
    ).json()

    project = client.post(
        "/projects", json={"name": "AWS 배포", "career_related": True}
    ).json()
    assert project["skills"] == []

    client.post(f"/projects/{project['id']}/skills/{skill['id']}")

    listed = client.get("/projects").json()[0]

    assert [s["name"] for s in listed["skills"]] == ["AWS"]
