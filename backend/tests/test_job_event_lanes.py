"""채용 행사 — 공고가 아니라 가는 날이다."""

from datetime import date, datetime, timedelta

from app import models
from app.services import opportunity as opportunity_service
from app.services import today as today_service


def _event(db, days, status="discovered"):
    event = models.Opportunity(
        source="work24_event", title="2026 성남시 청년 채용박람회", opportunity_type="job_event",
        status=status, deadline=datetime.now() + timedelta(days=days),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def test_an_upcoming_event_is_left_for_a_person_to_decide(db_session):
    match = opportunity_service.build_match(db_session, _event(db_session, 5), priority_entries=[])

    assert match["lane"] == "review"
    # 요구 스킬이 없어 점수는 낮지만 "지금은 아니에요" 에 묻지 않는다.
    assert match["recommendation"] == "consider"


def test_a_past_event_is_archived_as_a_past_event(db_session):
    match = opportunity_service.build_match(db_session, _event(db_session, -1), priority_entries=[])

    assert (match["lane"], match["archive_reason"]) == ("archived", "지난 행사")
    assert match["recommendation"] == "skip"


def test_today_asks_whether_to_attend_not_whether_to_apply(db_session):
    event = _event(db_session, 2, status="interested")

    candidates = today_service._deadline_candidates(db_session, date.today())

    assert [c["title"] for c in candidates] == [f"참석할지 정하기 — {event.title}"]
    assert candidates[0]["reason"] == "채용 행사까지 2일 남았습니다."
