"""적어 둔 생각 — 그리고 앱이 아는 것 중 그 생각에 닿는 것.

수현: "요즘 생각 고민이나 이런 거, 대학원을 갈지 말지 고민하는 거
얘는 모르잖아."

앱은 할 일 · 공고 · 스킬 · 증거를 안다. 그런데 무엇을 고민 중인지는
어디에도 없었다. 그게 가장 큰 결정인데도 그렇다.
"""

from app import models


def test_a_thought_is_kept_with_where_it_came_from(client):
    created = client.post("/thoughts", json={
        "kind": "idea",
        "body": "추천시스템 수업에서 나온 것 — 장기 취향과 현재 의도를 나눠 보기",
        "source": "추천시스템 수업",
    })

    assert created.status_code == 201
    body = created.json()
    assert body["kind_label"] == "해 볼 만한 것"
    assert body["source"] == "추천시스템 수업"
    assert body["status"] == "open"


def test_open_questions_come_first(client):
    client.post("/thoughts", json={"kind": "note", "body": "메모"})
    client.post("/thoughts", json={"kind": "question", "body": "대학원 갈지 말지"})

    listing = client.get("/thoughts").json()

    assert listing["thoughts"][0]["kind"] == "question"
    assert listing["open_questions"] == 1


def test_deciding_records_what_was_decided(client):
    thought = client.post("/thoughts", json={
        "kind": "question", "body": "코테를 계속할지",
    }).json()

    decided = client.post(f"/thoughts/{thought['id']}/decide", json={
        "decision": "계속한다 — 공고 절반이 코테를 본다",
    }).json()

    assert decided["status"] == "decided"
    assert "공고 절반" in decided["decision"]
    assert decided["decided_at"] is not None
    assert decided["open_days"] is None


def test_an_empty_decision_reopens_it(client):
    """되돌릴 데가 없으면 닫기를 망설이게 된다."""
    thought = client.post("/thoughts", json={
        "kind": "question", "body": "대학원",
    }).json()
    client.post(f"/thoughts/{thought['id']}/decide", json={"decision": "간다"})

    reopened = client.post(f"/thoughts/{thought['id']}/decide",
                           json={"decision": ""}).json()

    assert reopened["status"] == "open"
    assert reopened["decision"] == ""
    assert reopened["decided_at"] is None


def test_a_grad_school_question_gets_the_blocked_postings_as_evidence(
    client, db_session
):
    """이 앱이 메모장과 다른 지점. "대학원을 갈지 말지" 는 느낌으로 정할
    일이 아니다 — 석박사 요건에 막힌 공고가 몇 건인지가 이미 앱 안에 있다.
    """
    skill = models.Skill(name="Computer Vision", category="ml")
    db_session.add(skill)
    db_session.flush()

    posting = models.Opportunity(
        opportunity_type="job", title="Research Scientist", organization="KRAFTON",
        source="manual", status="discovered", blocked_reason="석박사 요건",
        description="자격요건\n딥러닝 관련 분야 석/박사 졸업 이상",
    )
    posting.skills.append(skill)
    db_session.add(posting)
    db_session.commit()

    thought = client.post("/thoughts", json={
        "kind": "question", "body": "대학원을 갈지 말지 고민 중",
    }).json()

    evidence = thought["evidence"]
    assert evidence is not None
    assert evidence["postings"] == 1
    assert evidence["organizations"] == ["KRAFTON"]
    assert "Computer Vision" in evidence["top_skills"]
    assert "석/박사" in evidence["degree_lines"][0]


def test_an_unrelated_thought_gets_no_evidence(client, db_session):
    """억지로 갖다 붙이면 근거가 아니라 장식이 된다."""
    thought = client.post("/thoughts", json={
        "kind": "question", "body": "점심에 뭘 먹을지",
    }).json()

    assert thought["evidence"] is None


def test_evidence_is_not_invented_when_nothing_is_blocked(client):
    """막힌 공고가 없으면 붙일 근거도 없다."""
    thought = client.post("/thoughts", json={
        "kind": "question", "body": "석사 진학을 할지",
    }).json()

    assert thought["evidence"] is None
