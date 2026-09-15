"""Opportunity / Experience / Portfolio / Application API."""


# --------------------------------
# Opportunity
# --------------------------------

def test_opportunity_crud(client):
    created = client.post(
        "/opportunities",
        json={
            "opportunity_type": "competition",
            "title": "AI Data Competition",
            "organization": "Kaggle",
            "source": "mock",
            "source_external_id": "abc-1",
        },
    )

    assert created.status_code == 201

    opportunity = created.json()
    assert opportunity["status"] == "discovered"

    assert len(client.get("/opportunities").json()) == 1
    assert len(client.get("/opportunities?opportunity_type=job").json()) == 0
    assert len(client.get("/opportunities?source=mock").json()) == 1

    updated = client.patch(
        f"/opportunities/{opportunity['id']}",
        json={"status": "interested"},
    ).json()

    assert updated["status"] == "interested"
    assert updated["title"] == "AI Data Competition"


def test_opportunity_type_is_validated(client):
    response = client.post(
        "/opportunities",
        json={
            "opportunity_type": "부트캠프",
            "title": "X",
            "source": "mock",
        },
    )

    assert response.status_code == 422


def test_duplicate_source_id_returns_409(client):
    payload = {
        "opportunity_type": "job",
        "title": "X",
        "source": "mock",
        "source_external_id": "same",
    }

    assert client.post("/opportunities", json=payload).status_code == 201

    duplicate = client.post("/opportunities", json=payload)

    assert duplicate.status_code == 409


def test_creating_a_job_also_creates_the_opportunity(client):
    """수요 집계의 모수는 Opportunity 하나다.

    Job 으로 들어온 것도 거기 있어야 두 화면이 같은 수를 말한다.
    전에는 Opportunity -> Job 한 방향만 있어서 분모가 갈렸다.
    """
    skill = client.post(
        "/skills", json={"name": "AWS", "category": "cloud"}
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "Mock Co", "title": "Data Intern", "role": "data"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    opportunities = client.get("/opportunities").json()
    mirrored = [
        item for item in opportunities if item["legacy_job_id"] == job["id"]
    ]

    assert len(mirrored) == 1
    assert mirrored[0]["title"] == "Data Intern"
    assert mirrored[0]["opportunity_type"] == "job"

    # 스킬 연결도 따라와야 수요로 잡힌다.
    priority = client.get("/analytics/learning-priority").json()
    assert priority["total_demand"] == 1
    assert priority["learning_priority"][0]["demand_count"] == 1


def _make_experience(client, title="Data Station"):
    response = client.post(
        "/experiences",
        json={
            "experience_type": "project",
            "title": title,
            "problem": "카드 이탈 분석",
            "role": "데이터 분석/모델링",
            "actions": "전처리, EDA, RandomForest",
            "results": "우수상",
            "technologies": "Python, Pandas",
            "metrics": "F1 0.82",
            "tags": "#data-analysis",
        },
    )

    assert response.status_code == 201

    return response.json()


def test_experience_keeps_technologies_and_tags(client):
    """Mission 021 에서 추가한 필드가 실제로 저장되는지.

    이 필드들이 없으면 Portfolio 승격 시 기술스택이 사라진다.
    """
    experience = _make_experience(client)

    assert experience["technologies"] == "Python, Pandas"
    assert experience["metrics"] == "F1 0.82"
    assert experience["tags"] == "#data-analysis"


def test_experience_skill_linking(client):
    experience = _make_experience(client)

    skill = client.post(
        "/skills",
        json={"name": "Python", "category": "lang"},
    ).json()

    client.post(f"/experiences/{experience['id']}/skills/{skill['id']}")

    linked = client.get(f"/experiences/{experience['id']}/skills").json()
    assert [s["name"] for s in linked] == ["Python"]

    client.delete(f"/experiences/{experience['id']}/skills/{skill['id']}")
    assert client.get(f"/experiences/{experience['id']}/skills").json() == []


def test_promote_experience_to_portfolio(client):
    """SPEC 12장: Experience -> PortfolioEntry 승격."""
    experience = _make_experience(client)

    response = client.post(
        f"/experiences/{experience['id']}/portfolio-entry"
    )

    assert response.status_code == 201

    entry = response.json()

    assert entry["title"] == "Data Station"
    assert entry["experience_id"] == experience["id"]
    assert entry["status"] == "draft"
    # 기술스택이 승격 과정에서 유실되지 않아야 한다
    assert entry["technologies"] == "Python, Pandas"
    assert entry["results"] == "우수상"


def test_promote_unknown_experience_returns_404(client):
    assert client.post("/experiences/999/portfolio-entry").status_code == 404


def test_portfolio_entries_are_ordered(client):
    for order, title in [(2, "C"), (0, "A"), (1, "B")]:
        client.post(
            "/portfolio-entries",
            json={"title": title, "display_order": order},
        )

    titles = [
        entry["title"]
        for entry in client.get("/portfolio-entries").json()
    ]

    assert titles == ["A", "B", "C"]


# --------------------------------
# Application
# --------------------------------

def _make_application(client):
    opportunity = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "Data Scientist Intern",
            "source": "mock",
        },
    ).json()

    response = client.post(
        "/applications",
        json={"opportunity_id": opportunity["id"]},
    )

    assert response.status_code == 201

    return response.json()


def test_application_defaults_to_interested(client):
    """기본 상태가 SPEC 17장 목록 안의 값이어야 한다."""
    application = _make_application(client)

    assert application["status"] == "interested"


def test_application_requires_a_target(client):
    response = client.post("/applications", json={})

    assert response.status_code == 422


def test_application_status_is_validated(client):
    application = _make_application(client)

    assert client.patch(
        f"/applications/{application['id']}",
        json={"status": "planned"},
    ).status_code == 422

    ok = client.patch(
        f"/applications/{application['id']}",
        json={"status": "document_pass"},
    )

    assert ok.status_code == 200
    assert ok.json()["status"] == "document_pass"


def test_application_rejects_unknown_opportunity(client):
    response = client.post("/applications", json={"opportunity_id": 999})

    assert response.status_code == 404


def test_experience_match_upsert_and_ordering(client):
    application = _make_application(client)

    first = _make_experience(client, title="Data Station")
    second = _make_experience(client, title="Fake News")

    for experience, score in [(first, 92), (second, 79)]:
        response = client.put(
            f"/applications/{application['id']}"
            f"/experiences/{experience['id']}",
            json={
                "application_id": application["id"],
                "experience_id": experience["id"],
                "match_score": score,
            },
        )
        assert response.status_code == 200

    matches = client.get(
        f"/applications/{application['id']}/experiences"
    ).json()

    assert [m["match_score"] for m in matches] == [92.0, 79.0]

    # 같은 조합을 다시 보내면 새로 만들지 않고 갱신한다
    client.put(
        f"/applications/{application['id']}/experiences/{first['id']}",
        json={
            "application_id": application["id"],
            "experience_id": first["id"],
            "match_score": 50,
            "match_notes": "재평가",
        },
    )

    matches = client.get(
        f"/applications/{application['id']}/experiences"
    ).json()

    assert len(matches) == 2
    assert matches[0]["match_score"] == 79.0


def test_match_score_bounds(client):
    application = _make_application(client)
    experience = _make_experience(client)

    response = client.put(
        f"/applications/{application['id']}/experiences/{experience['id']}",
        json={
            "application_id": application["id"],
            "experience_id": experience["id"],
            "match_score": 150,
        },
    )

    assert response.status_code == 422


# --------------------------------
# Cover Letter
# --------------------------------

def test_cover_letter_answer_versioning(client):
    """SPEC 19장: 답변은 버전으로 쌓이고 최신 하나만 current."""
    application = _make_application(client)

    question = client.post(
        "/cover-letter-questions",
        json={
            "application_id": application["id"],
            "question": "지원 동기를 작성해주세요.",
            "character_limit": 500,
        },
    ).json()

    first = client.post(
        f"/cover-letter-questions/{question['id']}/answers",
        json={"question_id": question["id"], "draft": "초안 1"},
    ).json()

    assert first["version"] == 1
    assert first["is_current"] is True

    second = client.post(
        f"/cover-letter-questions/{question['id']}/answers",
        json={"question_id": question["id"], "draft": "초안 2"},
    ).json()

    assert second["version"] == 2
    assert second["is_current"] is True

    answers = client.get(
        f"/cover-letter-questions/{question['id']}/answers"
    ).json()

    assert [a["version"] for a in answers] == [1, 2]
    assert [a["is_current"] for a in answers] == [False, True]

    current = client.get(
        f"/cover-letter-questions/{question['id']}/answers?current_only=true"
    ).json()

    assert len(current) == 1
    assert current[0]["draft"] == "초안 2"


def test_cover_letter_character_limit_is_enforced(client):
    application = _make_application(client)

    question = client.post(
        "/cover-letter-questions",
        json={
            "application_id": application["id"],
            "question": "지원 동기",
            "character_limit": 10,
        },
    ).json()

    response = client.post(
        f"/cover-letter-questions/{question['id']}/answers",
        json={"question_id": question["id"], "draft": "가" * 11},
    )

    assert response.status_code == 422
    assert "10자" in response.json()["detail"]

    ok = client.post(
        f"/cover-letter-questions/{question['id']}/answers",
        json={"question_id": question["id"], "draft": "가" * 10},
    )

    assert ok.status_code == 201


def test_duplicate_question_position_returns_409(client):
    application = _make_application(client)

    payload = {
        "application_id": application["id"],
        "question": "지원 동기",
        "position": 0,
    }

    assert client.post(
        "/cover-letter-questions", json=payload
    ).status_code == 201

    assert client.post(
        "/cover-letter-questions", json=payload
    ).status_code == 409


def test_deleting_application_removes_questions(client):
    application = _make_application(client)

    client.post(
        "/cover-letter-questions",
        json={
            "application_id": application["id"],
            "question": "지원 동기",
        },
    )

    client.delete(f"/applications/{application['id']}")

    assert client.get("/cover-letter-questions").json() == []


def test_today_does_not_tell_you_to_study_for_zero_minutes(
    client, db_session
):
    """분량을 모르는 자료를 넣으면 "0분 공부하세요" 라고 했다.

    종이책에는 duration_minutes 가 없다. 0분은 아무 뜻이 없는
    지시다. 모르면 모른다고 하고 무엇을 채우면 되는지 말해야 한다.
    """
    from app import models

    skill = models.Skill(name="Machine Learning", category="ai")
    db_session.add(skill)
    db_session.flush()

    db_session.add(
        models.LearningResource(
            title="핸즈온 머신러닝",
            resource_type="book",
            duration_minutes=0,
            ownership="owned",
            skill_id=skill.id,
        )
    )
    db_session.commit()

    action = client.get("/today").json()["today_action"]

    assert "0 minutes" not in action
    assert "핸즈온 머신러닝" in action
    # 무엇을 채우면 되는지 말해야 한다
    assert "나누면" in action


def test_a_split_book_is_planned_by_chapter_not_by_the_whole_book(
    client, db_session
):
    """자료를 쪼개뒀으면 그 조각이 오늘의 단위다.

    "책 한 권을 읽으세요" 가 아니라 "3장을 45분" 이어야 한다
    (LearningResourceSegment 의 존재 이유). 쪼개뒀는데도 계획이
    책 전체를 통째로 올리면 그 모델이 있을 이유가 없다.
    """
    from datetime import date

    from app import models
    from app.services import today as today_service

    skill = models.Skill(name="Machine Learning", category="ai")
    db_session.add(skill)
    db_session.flush()

    book = models.LearningResource(
        title="핸즈온 머신러닝",
        resource_type="book",
        duration_minutes=0,
        ownership="owned",
        skill_id=skill.id,
    )
    db_session.add(book)
    db_session.flush()

    db_session.add_all([
        models.LearningResourceSegment(
            learning_resource_id=book.id, position=0,
            label="1장 한눈에 보는 머신러닝",
            estimated_minutes=45, status="completed",
        ),
        models.LearningResourceSegment(
            learning_resource_id=book.id, position=1,
            label="2장 머신러닝 프로젝트 처음부터 끝까지",
            estimated_minutes=45,
        ),
    ])
    db_session.commit()

    # 오늘 행동 — 끝낸 1장이 아니라 다음인 2장을 가리켜야 한다
    action = client.get("/today").json()["today_action"]

    assert "2장" in action
    assert "1장" not in action
    assert "45분" in action

    # 계획 후보도 마찬가지
    entries = [
        c for c in today_service.build_candidates(db_session, date.today())
        if c["task_type"] == "resource"
    ]

    assert entries
    assert "2장" in entries[0]["title"]
    assert entries[0]["minutes"] == 45


def test_it_says_in_korean_that_the_library_has_no_resource(
    client, db_session
):
    """수요는 있는데 가진 자료가 없을 때.

    이 앱은 새 자료를 추천하지 않기로 했다(README 의 "하지 않는 것").
    그렇다고 빈칸을 감추면 안 된다 — 구멍이 어디인지는 말해야 한다.

    그리고 한국어 앱이다. 여기만 "Find a learning resource for
    PyTorch" 라고 영어로 나오고 있었다.
    """
    from app import models

    skill = models.Skill(name="PyTorch", category="ai")
    db_session.add(skill)
    db_session.flush()

    opportunity = models.Opportunity(
        title="ML 공고",
        organization="어떤회사",
        opportunity_type="job",
        source="manual",
    )
    opportunity.skills.append(skill)
    db_session.add(opportunity)
    db_session.commit()

    action = client.get("/today").json()["today_action"]

    assert "PyTorch" in action
    assert "라이브러리에 없습니다" in action

    # 영어가 남아 있으면 안 된다
    for phrase in ("Find a", "Study ", "Work on ", "minutes"):
        assert phrase not in action
