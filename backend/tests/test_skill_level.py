"""스킬 레벨과 그 이력.

레벨을 바꿀 방법이 아예 없었다. /skills 에 POST 와 GET 뿐이었다.
그래서 9장을 다 읽어도 Machine Learning 은 레벨 0 · 400점 그대로였다.
점수가 시장수요 x 격차 x 증거인데 격차가 안 움직이니, 배운 것이
우선순위에 하나도 반영되지 않았다.
"""

from datetime import datetime

from app import models
from app.services import priority, review


def _skill(db, level=0):
    skill = models.Skill(name="Machine Learning", category="ai", level=level)
    db.add(skill)
    db.commit()

    return skill


def test_level_can_be_changed_at_all(client, db_session):
    skill = _skill(db_session)

    response = client.patch(f"/skills/{skill.id}", json={"level": 2})

    assert response.status_code == 200
    assert response.json()["level"] == 2


def test_learning_actually_lowers_the_priority(client, db_session):
    """이 기능이 존재하는 이유. 배우면 점수가 내려가야 한다."""
    skill = _skill(db_session)

    opportunity = models.Opportunity(
        title="ML 공고", organization="어떤회사",
        opportunity_type="job", source="manual",
    )
    opportunity.skills.append(skill)
    db_session.add(opportunity)
    db_session.commit()

    before = priority.build_skill_priorities(db_session)[0]["priority_score"]

    client.patch(f"/skills/{skill.id}", json={"level": 2})

    after = priority.build_skill_priorities(db_session)[0]["priority_score"]

    assert before == 400
    assert after < before


def test_the_change_is_recorded(client, db_session):
    skill = _skill(db_session)

    client.patch(f"/skills/{skill.id}", json={"level": 2})

    events = client.get(f"/skills/{skill.id}/level-events").json()

    assert len(events) == 1
    assert events[0]["from_level"] == 0
    assert events[0]["to_level"] == 2
    assert events[0]["source"] == "manual"


def test_saving_the_same_level_is_not_a_change(client, db_session):
    """같은 값으로 다시 저장한 것을 기록하면 이력이 잡음이 된다."""
    skill = _skill(db_session, level=2)

    client.patch(f"/skills/{skill.id}", json={"level": 2})
    client.patch(f"/skills/{skill.id}", json={"status": "learning"})

    assert client.get(f"/skills/{skill.id}/level-events").json() == []


def test_level_stays_inside_the_scale(client, db_session):
    """MAX_SKILL_LEVEL 을 넘으면 skill_gap 이 음수가 되어 점수가 뒤집힌다."""
    skill = _skill(db_session)

    assert client.patch(f"/skills/{skill.id}", json={"level": 9}).status_code == 422
    assert client.patch(f"/skills/{skill.id}", json={"level": -1}).status_code == 422


def test_other_fields_are_untouched_when_not_given(client, db_session):
    skill = _skill(db_session)
    skill.aliases = "머신러닝, ML"
    db_session.commit()

    client.patch(f"/skills/{skill.id}", json={"level": 1})

    db_session.refresh(skill)

    assert skill.aliases == "머신러닝, ML"
    assert skill.name == "Machine Learning"


def test_review_shows_what_went_up_this_month(db_session):
    skill = _skill(db_session)

    db_session.add_all([
        models.SkillLevelEvent(
            skill_id=skill.id, from_level=0, to_level=1,
            changed_at=datetime(2026, 9, 5),
        ),
        models.SkillLevelEvent(
            skill_id=skill.id, from_level=1, to_level=2,
            changed_at=datetime(2026, 9, 22),
        ),
    ])
    db_session.commit()

    levels = review.build_review(db_session, 2026, 9)["levels"]

    # 0 → 1 → 2 는 두 번 오른 게 아니라 "0에서 2로" 한 줄이다
    assert levels == [
        {"skill": "Machine Learning", "from": 0, "to": 2, "at": "2026-09-22"}
    ]


def test_a_level_that_came_back_is_not_a_change(db_session):
    skill = _skill(db_session)

    db_session.add_all([
        models.SkillLevelEvent(
            skill_id=skill.id, from_level=0, to_level=1,
            changed_at=datetime(2026, 9, 5),
        ),
        models.SkillLevelEvent(
            skill_id=skill.id, from_level=1, to_level=0,
            changed_at=datetime(2026, 9, 6),
        ),
    ])
    db_session.commit()

    assert review.build_review(db_session, 2026, 9)["levels"] == []


def test_review_no_longer_claims_it_cannot_track_levels(db_session):
    assert "skill_level_history" not in review.build_review(
        db_session, 2026, 9
    )["not_tracked"]
