"""기회 화면의 칸 — 판단이 끝난 기회는 판단할 목록에서 빠진다."""

from datetime import datetime, timedelta

import pytest

from app import models
from app.services import opportunity as opportunity_service


def _opportunity(db, status="discovered", days=5, application=None):
    opportunity = models.Opportunity(
        source="manual", title="인공지능 (AI부문)", organization="한빛전자",
        opportunity_type="job", status=status,
        deadline=datetime.now() + timedelta(days=days) if days is not None else None,
    )
    db.add(opportunity)
    db.flush()
    if application:
        db.add(models.Application(opportunity_id=opportunity.id, status=application))
    db.commit()
    db.refresh(opportunity)
    return opportunity_service.build_match(db, opportunity, priority_entries=[])


@pytest.mark.parametrize(
    "application, reason",
    [("withdrawn", "지원서 철회"), ("rejected", "불합격"), ("accepted", "합격")],
)
def test_finished_applications_go_to_the_archive(db_session, application, reason):
    match = _opportunity(db_session, days=0, application=application)

    assert (match["lane"], match["archive_reason"]) == ("archived", reason)
    # 오늘 마감이어도 끝난 기회에 "지금 할 만해요" 를 붙이지 않는다.
    assert match["recommendation"] == "skip"


def test_an_active_application_is_its_own_lane(db_session):
    match = _opportunity(db_session, days=None, application="applied")
    assert (match["lane"], match["archive_reason"]) == ("applied", None)


def test_a_passed_deadline_without_an_application_is_archived(db_session):
    match = _opportunity(db_session, days=-2)
    assert (match["lane"], match["archive_reason"]) == ("archived", "마감 지남")


def test_closed_on_hold_and_review(db_session):
    assert _opportunity(db_session, status="closed")["archive_reason"] == "직접 닫음"
    assert _opportunity(db_session, status="on_hold")["lane"] == "on_hold"
    assert _opportunity(db_session, status="not_interested")["lane"] == "not_interested"
    assert _opportunity(db_session)["lane"] == "review"


def test_the_archive_can_still_delete_only_without_applications(client, db_session):
    loose = _opportunity(db_session, status="closed")
    applied = _opportunity(db_session, days=0, application="withdrawn")

    assert client.delete(f"/opportunities/{applied['opportunity_id']}").status_code == 409
    assert client.delete(f"/opportunities/{loose['opportunity_id']}").status_code == 200
