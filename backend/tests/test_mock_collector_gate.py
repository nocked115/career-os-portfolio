"""운영에서는 mock 수집원이 돌면 안 된다.

배포본에 진짜 공고 3건만 남겨뒀는데, 다시 확인해보니 목업 공고
둘과 legacy Job 하나가 되살아나 있었다. 스케줄러가 매일 08:00 에
collect_all 을 돌리고 거기에 mock 수집기가 물려 있었다.

가짜 공고가 수요의 분모에 들어가면 그 위에서 계산된 "오늘 뭘
하면 되지?" 가 통째로 틀린다.
"""

from app import models
from app.collectors import mock
from app.services import opportunity as opportunity_service


def test_mock_is_off_in_production(monkeypatch):
    monkeypatch.setenv("CAREER_OS_ENV", "production")

    assert mock.is_available() is False


def test_mock_is_on_for_local_development(monkeypatch):
    monkeypatch.delenv("CAREER_OS_ENV", raising=False)

    assert mock.is_available() is True


def test_production_collection_creates_nothing(db_session, monkeypatch):
    """실사용 배포본의 공고 목록이 저절로 늘어나면 안 된다."""
    monkeypatch.setenv("CAREER_OS_ENV", "production")

    before = db_session.query(models.Opportunity).count()

    result = opportunity_service.collect_all(db_session)

    assert result["sources"] == []
    assert result["created"] == 0
    assert db_session.query(models.Opportunity).count() == before


def test_local_collection_still_works(db_session, monkeypatch):
    """로컬에서는 그대로 돌아야 한다. 참고 구현이자 개발용이다."""
    monkeypatch.delenv("CAREER_OS_ENV", raising=False)

    result = opportunity_service.collect_all(db_session)

    assert result["created"] > 0
    assert db_session.query(models.Opportunity).count() > 0
