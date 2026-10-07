"""수요로 세는 공고 — 분자와 분모가 같은 모집단이어야 한다.

전에는 모수만 걸렀고 스킬별 건수는 전부 셌다. 그래서 비율이 모집단이 다른 두 수의
나눗셈이었고, **이미 마감된 공고**의 스킬이 "지금 중요한 것" 으로 올라왔다.
"""

from datetime import date, timedelta

from app import models
from app.services import market as market_service, priority as priority_service


def _skill(db_session, name, level=0):
    skill = models.Skill(name=name, category="data", level=level)
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(skill)
    return skill


def _opportunity(db_session, title, skills=(), days=None, status="discovered",
                 filtered_reason=""):
    row = models.Opportunity(
        opportunity_type="job",
        title=title,
        source="test",
        status=status,
        filtered_reason=filtered_reason,
        deadline=None if days is None else date.today() + timedelta(days=days),
    )
    row.skills.extend(skills)
    db_session.add(row)
    db_session.commit()
    return row


def test_a_closed_posting_is_not_demand(db_session):
    """지원할 수 없는 공고는 지금의 수요가 아니다."""
    skill = _skill(db_session, "LLM")
    _opportunity(db_session, "열린 공고", [skill], days=10)
    _opportunity(db_session, "마감 지난 공고", [skill], days=-1)

    signals = market_service.build_signals(db_session)
    llm = next(s for s in signals if s["skill"] == "LLM")

    assert market_service.count_opportunities(db_session) == 1
    assert llm["opportunity_count"] == 1
    assert llm["percentage"] == 100


def test_a_posting_with_no_deadline_still_counts(db_session):
    """상시채용은 아직 열려 있다."""
    skill = _skill(db_session, "SQL")
    _opportunity(db_session, "상시채용", [skill], days=None)

    assert market_service.count_opportunities(db_session) == 1
    signals = market_service.build_signals(db_session)
    assert next(s for s in signals if s["skill"] == "SQL")["opportunity_count"] == 1


def test_a_posting_i_turned_down_is_not_demand(db_session):
    """관심 없음으로 내린 것은 내 수요가 아니다 (CJ 계열사 제한 같은 경우)."""
    skill = _skill(db_session, "Infrastructure")
    _opportunity(db_session, "갈 수 없는 곳", [skill], days=10, status="not_interested")

    assert market_service.count_opportunities(db_session) == 0
    signals = market_service.build_signals(db_session)
    assert next(s for s in signals if s["skill"] == "Infrastructure")["opportunity_count"] == 0


def test_numerator_and_denominator_use_the_same_population(db_session):
    """비율이 100% 를 넘지 않는다 — 전에는 넘을 수 있었다."""
    skill = _skill(db_session, "Python")
    _opportunity(db_session, "열린 것", [skill], days=5)
    for i in range(3):
        _opportunity(db_session, f"마감 지난 것 {i}", [skill], days=-5)

    signals = market_service.build_signals(db_session)
    python = next(s for s in signals if s["skill"] == "Python")

    assert python["opportunity_count"] == 1
    assert python["percentage"] == 100


def test_priority_ignores_closed_postings(db_session):
    """우선순위도 같은 모집단을 본다."""
    closed_only = _skill(db_session, "MLOps")
    open_too = _skill(db_session, "Data Analysis")

    _opportunity(db_session, "마감 지난 공고", [closed_only], days=-3)
    _opportunity(db_session, "열린 공고", [open_too], days=7)

    entries = {e["skill"].name: e for e in priority_service.build_skill_priorities(db_session)}

    assert entries["MLOps"]["demand_count"] == 0
    assert entries["Data Analysis"]["demand_count"] == 1
    assert entries["Data Analysis"]["priority_score"] > entries["MLOps"]["priority_score"]
