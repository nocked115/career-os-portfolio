"""Application Workspace — Phase 5.

절대 규칙: 없는 경험을 지어내지 않는다.
할 수 없는 것(문장 생성·설득력 판단)은 할 수 없다고 말한다.
"""

from app.services import application as application_service
from app.services import jd as jd_service


def _skill(client, name, level=0):
    return client.post(
        "/skills", json={"name": name, "category": "x", "level": level}
    ).json()


def _application(client, description="", title="Data Scientist Intern"):
    opportunity = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": title,
            "source": "manual",
            "description": description,
        },
    ).json()

    return client.post(
        "/applications", json={"opportunity_id": opportunity["id"]}
    ).json()


def _experience(client, title, technologies=""):
    return client.post(
        "/experiences",
        json={
            "experience_type": "project",
            "title": title,
            "technologies": technologies,
        },
    ).json()


# --------------------------------
# 단어 경계 — 기존 매칭의 결함
# --------------------------------

def test_substring_no_longer_matches_a_bigger_word(db_session):
    """기존 collector 는 "Go" 를 "Google" 에서도 찾았다."""
    from app import models

    db_session.add(models.Skill(name="Go", category="lang", level=0))
    db_session.commit()

    assert jd_service.extract_skills(db_session, "Google 에서 일했습니다") == []
    assert len(jd_service.extract_skills(db_session, "Go 를 씁니다")) == 1


def test_c_does_not_match_css(db_session):
    from app import models

    db_session.add(models.Skill(name="C", category="lang", level=0))
    db_session.commit()

    assert jd_service.extract_skills(db_session, "CSS 를 다룹니다") == []


def test_matching_is_case_insensitive(db_session):
    from app import models

    db_session.add(models.Skill(name="Python", category="lang", level=0))
    db_session.commit()

    assert len(jd_service.extract_skills(db_session, "python 필수")) == 1


def test_empty_text_finds_nothing(db_session):
    assert jd_service.extract_skills(db_session, "") == []


# --------------------------------
# 강조도
# --------------------------------

def test_more_mentions_means_more_emphasis(client):
    _skill(client, "Python")
    _skill(client, "Rust")

    application = _application(
        client,
        description="Python 필수. Python 경험자 우대. Rust 도 알면 좋음.",
    )

    body = client.get(
        f"/applications/{application['id']}/analysis"
    ).json()

    skills = {s["skill"]: s for s in body["required_skills"]}

    assert skills["Python"]["mentions"] == 2
    assert skills["Rust"]["mentions"] == 1
    assert skills["Python"]["emphasis"] > skills["Rust"]["emphasis"]
    assert body["required_skills"][0]["skill"] == "Python"


def test_strength_reflects_my_level(client):
    _skill(client, "Python", level=3)
    _skill(client, "SQL", level=1)
    _skill(client, "Rust", level=0)

    application = _application(client, description="Python, SQL, Rust")

    body = client.get(
        f"/applications/{application['id']}/analysis"
    ).json()
    strength = {s["skill"]: s["strength"] for s in body["required_skills"]}

    assert strength["Python"] == "strong"
    assert strength["SQL"] == "medium"
    assert strength["Rust"] == "gap"
    assert body["gap_skills"] == ["Rust"]


def test_match_score_is_the_covered_emphasis(client):
    _skill(client, "Python", level=3)
    _skill(client, "Rust", level=0)

    application = _application(client, description="Python 과 Rust")

    body = client.get(
        f"/applications/{application['id']}/analysis"
    ).json()

    assert 0 < body["match_score"] < 100


# --------------------------------
# 한계를 숨기지 않는다
# --------------------------------

def test_empty_description_says_so(client):
    application = _application(client, description="")

    body = client.get(
        f"/applications/{application['id']}/analysis"
    ).json()

    assert body["has_description"] is False
    assert "본문이 비어 있어" in " ".join(body["notes"])


def test_unregistered_skills_cannot_be_found(client):
    application = _application(client, description="Kubernetes 경험 필수")

    body = client.get(
        f"/applications/{application['id']}/analysis"
    ).json()

    assert body["required_skills"] == []
    assert "스킬을 먼저 등록하면" in " ".join(body["notes"])


def test_the_method_limit_is_stated(client):
    _skill(client, "Python")
    application = _application(client, description="Python 필수")

    notes = " ".join(
        client.get(f"/applications/{application['id']}/analysis").json()["notes"]
    )

    assert "등록되지 않은 역량은 찾지 못합니다" in notes


# --------------------------------
# 경험 매칭 — 억지로 추천하지 않는다
# --------------------------------

def test_unrelated_experience_is_not_recommended(client):
    _skill(client, "Python")
    _experience(client, "요리 동아리", technologies="Cooking")

    application = _application(client, description="Python 필수")

    body = client.get(
        f"/applications/{application['id']}/analysis"
    ).json()

    assert body["recommended_experiences"] == []
    assert "억지로 추천하지 않습니다" in " ".join(body["notes"])


def test_covering_experience_is_recommended(client):
    _skill(client, "Python")
    _experience(client, "데이터 분석 프로젝트", technologies="Python, Pandas")

    application = _application(client, description="Python 필수")

    body = client.get(
        f"/applications/{application['id']}/analysis"
    ).json()

    top = body["recommended_experiences"][0]
    assert top["title"] == "데이터 분석 프로젝트"
    assert top["score"] == 100
    assert top["covered"] == ["Python"]


def test_auto_match_saves_scores(client):
    """점수를 사람이 직접 넣던 것을 자동으로 채운다."""
    _skill(client, "Python")
    _experience(client, "데이터 분석", technologies="Python")

    application = _application(client, description="Python 필수")

    body = client.post(
        f"/applications/{application['id']}/auto-match"
    ).json()

    assert body["matched"] == 1

    matches = client.get(
        f"/applications/{application['id']}/experiences"
    ).json()

    assert matches[0]["match_score"] == 100
    assert "자동 매칭" in matches[0]["match_notes"]


def test_auto_match_keeps_handwritten_notes(client):
    """사람이 쓴 메모를 덮어쓰지 않는다."""
    _skill(client, "Python")
    experience = _experience(client, "데이터 분석", technologies="Python")
    application = _application(client, description="Python 필수")

    client.put(
        f"/applications/{application['id']}/experiences/{experience['id']}",
        json={
            "application_id": application["id"],
            "experience_id": experience["id"],
            "match_score": 10,
            "match_notes": "직접 쓴 메모",
        },
    )

    client.post(f"/applications/{application['id']}/auto-match")

    matches = client.get(
        f"/applications/{application['id']}/experiences"
    ).json()

    assert matches[0]["match_notes"] == "직접 쓴 메모"
    assert matches[0]["match_score"] == 100


# --------------------------------
# 상태 전이
# --------------------------------

def test_allowed_transitions_are_listed(client):
    application = _application(client)

    body = client.get(
        f"/applications/{application['id']}/transitions"
    ).json()

    assert body["current"] == "interested"
    assert body["allowed"] == ["preparing", "withdrawn"]
    assert body["is_terminal"] is False


def test_forward_move_works(client):
    application = _application(client)

    body = client.post(
        f"/applications/{application['id']}/move?status=preparing"
    ).json()

    assert body["from"] == "interested"
    assert body["to"] == "preparing"
    assert body["forced"] is False


def test_skipping_a_step_is_blocked(client):
    application = _application(client)

    response = client.post(
        f"/applications/{application['id']}/move?status=applied"
    )

    assert response.status_code == 409
    assert "로만 갈 수 있습니다" in response.json()["detail"]


def test_terminal_state_cannot_continue(client):
    application = _application(client)

    for step in ("preparing", "ready", "applied", "rejected"):
        client.post(f"/applications/{application['id']}/move?status={step}")

    response = client.post(
        f"/applications/{application['id']}/move?status=interview"
    )

    assert response.status_code == 409
    assert "끝난 상태" in response.json()["detail"]


def test_force_allows_a_correction(client):
    """잘못 누른 것을 되돌릴 길은 남긴다."""
    application = _application(client)

    body = client.post(
        f"/applications/{application['id']}/move?status=applied&force=true"
    ).json()

    assert body["to"] == "applied"
    assert body["forced"] is True


def test_unknown_status_is_rejected(client):
    application = _application(client)

    assert client.post(
        f"/applications/{application['id']}/move?status=hired"
    ).status_code == 422


def test_transition_table_is_consistent():
    """모든 목적지가 정의된 상태여야 한다."""
    for current, targets in application_service.TRANSITIONS.items():
        for target in targets:
            assert target in application_service.TRANSITIONS, (
                f"{current} → {target} 의 목적지가 정의되지 않았다"
            )


# --------------------------------
# 자소서 지원
# --------------------------------

def _question(client, application, limit=500):
    return client.post(
        "/cover-letter-questions",
        json={
            "application_id": application["id"],
            "question": "지원 동기를 작성해주세요.",
            "character_limit": limit,
            "position": 0,
        },
    ).json()


def test_outline_refuses_without_a_covering_experience(client):
    """관련 없는 경험으로 구조를 짜면 자소서가 더 나빠진다."""
    _skill(client, "Python")
    application = _application(client, description="Python 필수")
    question = _question(client, application)

    body = client.get(
        f"/cover-letter-questions/{question['id']}/outline"
    ).json()

    assert body["sections"] == []
    assert "경험을 먼저 등록하세요" in body["message"]


def test_outline_uses_the_best_experience(client):
    _skill(client, "Python")
    client.post(
        "/experiences",
        json={
            "experience_type": "project",
            "title": "데이터 분석",
            "technologies": "Python",
            "problem": "이탈 예측이 필요했다",
            "role": "모델링 담당",
            "actions": "전처리와 모델 학습",
            "results": "정확도 87%",
        },
    )

    application = _application(client, description="Python 필수")
    question = _question(client, application, limit=500)

    body = client.get(
        f"/cover-letter-questions/{question['id']}/outline"
    ).json()

    assert body["based_on"]["title"] == "데이터 분석"

    sections = {s["key"]: s for s in body["sections"]}
    assert sections["situation"]["content"] == "이탈 예측이 필요했다"
    assert sections["results"]["content"] == "정확도 87%"

    # 분량 배분 합계가 제한과 맞아야 한다
    assert sum(s["suggested_chars"] for s in body["sections"]) == 500
    assert body["message"] is None


def test_outline_reports_empty_experience_fields(client):
    _skill(client, "Python")
    client.post(
        "/experiences",
        json={
            "experience_type": "project",
            "title": "데이터 분석",
            "technologies": "Python",
            "actions": "모델 학습",
        },
    )

    application = _application(client, description="Python 필수")
    question = _question(client, application)

    body = client.get(
        f"/cover-letter-questions/{question['id']}/outline"
    ).json()

    assert "지어내지 않습니다" in body["message"]
    assert "결과" in body["message"]


# --------------------------------
# 점검 — 셀 수 있는 것만 본다
# --------------------------------

def test_review_flags_over_limit(client):
    application = _application(client)
    question = _question(client, application, limit=100)

    body = client.post(
        f"/cover-letter-questions/{question['id']}/review",
        params={"draft": "가" * 150},
    ).json()

    length_check = next(c for c in body["checks"] if c["key"] == "length")
    assert length_check["ok"] is False
    assert "50자 넘었습니다" in length_check["message"]


def test_review_flags_too_short(client):
    application = _application(client)
    question = _question(client, application, limit=500)

    body = client.post(
        f"/cover-letter-questions/{question['id']}/review",
        params={"draft": "짧다"},
    ).json()

    length_check = next(c for c in body["checks"] if c["key"] == "length")
    assert length_check["ok"] is False
    assert "절반도" in length_check["message"]


def test_review_checks_the_answer_is_grounded(client):
    client.post(
        "/experiences",
        json={"experience_type": "project", "title": "데이터 분석"},
    )

    application = _application(client)
    question = _question(client, application, limit=50)

    without = client.post(
        f"/cover-letter-questions/{question['id']}/review",
        params={"draft": "열심히 하겠습니다"},
    ).json()
    grounded = next(c for c in without["checks"] if c["key"] == "grounded")
    assert grounded["ok"] is False

    with_it = client.post(
        f"/cover-letter-questions/{question['id']}/review",
        params={"draft": "데이터 분석 경험이 있습니다"},
    ).json()
    grounded = next(c for c in with_it["checks"] if c["key"] == "grounded")
    assert grounded["ok"] is True
    assert "데이터 분석" in grounded["message"]


def test_review_states_what_it_cannot_judge(client):
    """문체와 설득력은 판단하지 않는다고 말한다."""
    application = _application(client)
    question = _question(client, application)

    body = client.post(
        f"/cover-letter-questions/{question['id']}/review",
        params={"draft": "내용"},
    ).json()

    assert "문체와 설득력은 판단하지 않습니다" in body["note"]


def test_unknown_ids_return_404(client):
    assert client.get("/applications/9999/analysis").status_code == 404
    assert client.get("/cover-letter-questions/9999/outline").status_code == 404
