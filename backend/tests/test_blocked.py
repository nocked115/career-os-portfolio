"""지원 자격이 안 되는 공고.

수현: "공고 중에 석박사 요구조건에 안 맞아서 안 되는 거면 이건 어떻게
처리해야 하는 거야?"

수현 데이터에서 재 보니 Reinforcement Learning 수요 4건이 **전부**
석박사 자리였다. 2027-02 학사 졸업으로는 못 가는 자리가 그 스킬의 수요를
혼자 만들고 있었고, 앱은 거꾸로 그걸 공부하라고 말하고 있었다.
"""

from app import models
from app.services import market


def _skill(db, name):
    row = models.Skill(name=name, category="ai", level=0)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _posting(db, title, skills=(), blocked=""):
    row = models.Opportunity(
        opportunity_type="job", title=title, source="test",
        blocked_reason=blocked,
    )
    row.skills.extend(skills)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_a_blocked_posting_is_not_demand(db_session):
    """지원할 수 없는 공고는 지금의 수요가 아니다 — 마감 지난 것과 같다."""
    rl = _skill(db_session, "Reinforcement Learning")

    _posting(db_session, "열린 공고", [rl])
    _posting(db_session, "석사 필수", [rl], blocked="석사 이상 필수")

    assert market.count_opportunities(db_session) == 1

    signal = next(
        s for s in market.build_signals(db_session)
        if s["skill"] == "Reinforcement Learning"
    )
    assert signal["opportunity_count"] == 1


def test_blocked_postings_are_counted_not_deleted(db_session):
    """"4건 중 3건이 석사 요구" 를 말하려면 지우면 안 된다."""
    cv = _skill(db_session, "Computer Vision")

    _posting(db_session, "학사 가능", [cv])
    for i in range(3):
        _posting(db_session, f"석사 자리 {i}", [cv], blocked="석사 이상 필수")

    rows = market.blocked_by_skill(db_session)
    row = next(r for r in rows if r["skill"] == "Computer Vision")

    assert row["blocked"] == 3
    assert row["total"] == 4
    assert row["percentage"] == 75
    assert row["reasons"] == ["석사 이상 필수"]


def test_a_skill_entirely_blocked_comes_first(db_session):
    """"이 스킬은 거의 다 막혀 있다" 가 먼저 보여야 한다."""
    rl = _skill(db_session, "Reinforcement Learning")
    cv = _skill(db_session, "Computer Vision")

    for i in range(2):
        _posting(db_session, f"RL {i}", [rl], blocked="박사 우대 · 연구직")
    _posting(db_session, "CV 열림", [cv])
    _posting(db_session, "CV 막힘", [cv], blocked="석사 이상 필수")

    rows = market.blocked_by_skill(db_session)

    assert rows[0]["skill"] == "Reinforcement Learning"
    assert rows[0]["percentage"] == 100


def test_a_skill_with_nothing_blocked_is_not_listed(db_session):
    sql = _skill(db_session, "SQL")
    _posting(db_session, "열린 공고", [sql])

    assert [r["skill"] for r in market.blocked_by_skill(db_session)] == []


def test_the_endpoint_blocks_and_restores(client, db_session):
    rl = _skill(db_session, "Reinforcement Learning")
    posting = _posting(db_session, "연구직", [rl])

    body = client.post(
        f"/opportunities/{posting.id}/block", json={"reason": "석사 이상 필수"}
    ).json()
    assert body["blocked_reason"] == "석사 이상 필수"
    assert market.count_opportunities(db_session) == 0

    # 비워 보내면 되돌린다.
    client.post(f"/opportunities/{posting.id}/block", json={"reason": ""})
    db_session.expire_all()
    assert market.count_opportunities(db_session) == 1


def test_the_report_endpoint(client, db_session):
    cv = _skill(db_session, "Computer Vision")
    _posting(db_session, "열림", [cv])
    _posting(db_session, "막힘", [cv], blocked="석사 이상 필수")

    body = client.get("/analytics/blocked-skills").json()

    assert body["skills"][0]["skill"] == "Computer Vision"
    assert body["skills"][0]["blocked"] == 1
