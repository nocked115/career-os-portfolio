"""지원서 보드 — "그래서 지금 무엇을 해야 하지?"

다음 행동은 셀 수 있는 것으로만 정한다. 모자라면 모자라다고 말한다.
"""

from datetime import datetime, timedelta

from app import models
from app.services import jd as jd_service


def _skill(client, name, level=0):
    return client.post(
        "/skills", json={"name": name, "category": "x", "level": level}
    ).json()


def _application(client, title="데이터 분석가", description="", days=None):
    body = {
        "opportunity_type": "job",
        "title": title,
        "organization": "어떤회사",
        "source": "manual",
        "description": description,
    }

    if days is not None:
        body["deadline"] = (
            (datetime.now() + timedelta(days=days)).replace(microsecond=0).isoformat()
        )

    opportunity = client.post("/opportunities", json=body).json()

    return client.post(
        "/applications", json={"opportunity_id": opportunity["id"]}
    ).json()


def _question(client, application, position=0, limit=500):
    return client.post(
        "/cover-letter-questions",
        json={
            "application_id": application["id"],
            "question": f"{position + 1}번 문항",
            "character_limit": limit,
            "position": position,
        },
    ).json()


def _answer(client, question, draft):
    return client.post(
        f"/cover-letter-questions/{question['id']}/answers",
        json={"question_id": question["id"], "draft": draft},
    )


def _move(client, application, *statuses):
    for status in statuses:
        client.post(f"/applications/{application['id']}/move?status={status}")


def _board(client):
    response = client.get("/applications/board")
    assert response.status_code == 200
    return response.json()


def _card(board, application):
    return next(c for c in board["applications"] if c["id"] == application["id"])


# --------------------------------
# 다음 행동
# --------------------------------

def test_without_questions_the_next_step_is_to_register_them(client):
    application = _application(client)

    card = _card(_board(client), application)

    assert card["next_action"]["kind"] == "add_questions"
    assert "questions" in card["missing"]


def test_the_next_step_is_the_first_unwritten_question(client):
    application = _application(client)
    first = _question(client, application, position=0)
    second = _question(client, application, position=1)
    _answer(client, first, "가" * 300)

    card = _card(_board(client), application)

    assert (card["letter"]["answered"], card["letter"]["total"]) == (1, 2)
    assert card["next_action"]["label"] == "2번 문항 작성"
    assert card["next_action"]["question_id"] == second["id"]


def test_a_blank_answer_is_not_counted_as_written(client):
    application = _application(client)
    question = _question(client, application)
    _answer(client, question, "   ")

    card = _card(_board(client), application)

    assert card["letter"]["answered"] == 0
    assert card["next_action"]["kind"] == "write"


def test_a_short_answer_asks_for_revision(client):
    application = _application(client)
    question = _question(client, application, limit=500)
    _answer(client, question, "가" * 100)

    action = _card(_board(client), application)["next_action"]

    assert action["kind"] == "revise"
    assert "100/500자" in action["detail"]


def test_when_everything_is_written_the_step_moves_forward(client):
    """상태는 서버 규칙을 따라 한 칸씩만 권한다."""
    application = _application(client)
    question = _question(client, application, limit=500)
    _answer(client, question, "가" * 400)

    action = _card(_board(client), application)["next_action"]
    assert (action["kind"], action["target_status"]) == ("move", "preparing")

    _move(client, application, "preparing")
    action = _card(_board(client), application)["next_action"]
    assert action["target_status"] == "ready"

    _move(client, application, "ready")
    action = _card(_board(client), application)["next_action"]
    assert (action["kind"], action["target_status"]) == ("submit", "applied")


def test_waiting_for_a_result_is_not_offered_as_the_next_step(client):
    application = _application(client)
    _move(client, application, "preparing", "ready", "applied")

    board = _board(client)

    assert _card(board, application)["next_action"]["kind"] == "wait"
    assert board["summary"]["next"] is None


def test_terminal_applications_have_no_next_step(client):
    application = _application(client)
    _move(client, application, "withdrawn")

    board = _board(client)
    card = _card(board, application)

    assert card["is_terminal"] is True
    assert card["next_action"] is None
    assert board["summary"]["active"] == 0


# --------------------------------
# 요약
# --------------------------------

def test_the_summary_picks_the_nearest_deadline(client):
    _application(client, title="나중", days=10)
    sooner = _application(client, title="먼저", days=2)
    _application(client, title="날짜 없음")

    summary = _board(client)["summary"]

    assert summary["next"]["application_id"] == sooner["id"]
    assert summary["next"]["label"] == "자기소개서 문항 등록"
    assert summary["urgent"] == 1       # 7일 안은 "먼저" 하나


def test_the_summary_says_nothing_rather_than_guessing(client):
    summary = _board(client)["summary"]

    assert summary["next"] is None
    assert summary["active"] == 0


def test_writing_counts_applications_with_questions_left(client):
    partly = _application(client, title="일부")
    _answer(client, _question(client, partly, position=0), "가" * 300)
    _question(client, partly, position=1)

    _application(client, title="문항 없음")

    done = _application(client, title="다 씀")
    _answer(client, _question(client, done), "가" * 300)

    assert _board(client)["summary"]["writing"] == 1


def test_the_deadline_falls_back_to_the_posting(client):
    application = _application(client, days=5)

    card = _card(_board(client), application)
    assert (card["deadline_source"], card["days_left"]) == ("opportunity", 5)

    own = (datetime.now() + timedelta(days=3)).replace(microsecond=0).isoformat()
    client.patch(f"/applications/{application['id']}", json={"deadline": own})

    card = _card(_board(client), application)
    assert (card["deadline_source"], card["days_left"]) == ("application", 3)


# --------------------------------
# 매칭 — 분모와 근거
# --------------------------------

def test_match_is_reported_with_its_denominator(client):
    _skill(client, "Python", level=3)
    _skill(client, "Rust", level=0)
    application = _application(client, description="Python 과 Rust")

    match = _card(_board(client), application)["match"]

    assert match["available"] is True
    assert (match["have"], match["total"]) == (1, 2)
    strength = {s["skill"]: s["strength"] for s in match["skills"]}
    assert strength == {"Python": "strong", "Rust": "gap"}


def test_match_without_a_description_says_why(client):
    application = _application(client, description="")

    match = _card(_board(client), application)["match"]

    assert match["available"] is False
    assert "본문이 비어" in match["reason"]


def test_linked_skills_stand_in_when_the_text_finds_none(db_session):
    """"AI/Agent" 로 적힌 공고가 "AI Agent" 스킬을 못 찾았다. 실제로 그랬다."""
    skill = models.Skill(name="AI Agent", category="ai", level=1)
    posting = models.Opportunity(
        title="AI/Data 기획", organization="어떤회사",
        opportunity_type="job", source="manual",
        description="AI/Agent 서비스를 기획하고 운영합니다.",
    )
    posting.skills.append(skill)
    application = models.Application(opportunity=posting)
    db_session.add_all([skill, posting, application])
    db_session.commit()

    analysis = jd_service.analyze_application(db_session, application)

    assert analysis["basis"] == "linked"
    assert [s["skill"] for s in analysis["required_skills"]] == ["AI Agent"]
    assert "직접 연결한 스킬" in " ".join(analysis["notes"])


def test_text_matches_win_over_linked_skills(db_session):
    python = models.Skill(name="Python", category="lang", level=0)
    sql = models.Skill(name="SQL", category="data", level=0)
    posting = models.Opportunity(
        title="분석가", organization="어떤회사",
        opportunity_type="job", source="manual", description="Python 필수",
    )
    posting.skills.extend([python, sql])
    application = models.Application(opportunity=posting)
    db_session.add_all([python, sql, posting, application])
    db_session.commit()

    analysis = jd_service.analyze_application(db_session, application)

    assert analysis["basis"] == "text"
    assert [s["skill"] for s in analysis["required_skills"]] == ["Python"]


# --------------------------------
# 사용자 언어
# --------------------------------

def test_transition_messages_do_not_show_raw_status_values(client):
    application = _application(client)

    response = client.post(f"/applications/{application['id']}/move?status=applied")

    assert response.status_code == 409
    assert "'관심'" in response.json()["detail"]
    assert "interested" not in response.json()["detail"]


def test_the_board_route_is_not_read_as_an_id(client):
    assert client.get("/applications/board").status_code == 200
