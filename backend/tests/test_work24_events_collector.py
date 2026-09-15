"""고용24 채용행사 — 앞으로 열리는 수도권 박람회만, 담당자 연락처는 옮기지 않는다."""

import xml.etree.ElementTree as ET
from datetime import date, timedelta

import pytest

from app import models
from app.collectors import base, work24_events
from app.services import opportunity as opportunity_service


SOON = (date.today() + timedelta(days=10)).isoformat()
PAST = (date.today() - timedelta(days=10)).isoformat()

LIST_XML = f"""<empEvList><total>5</total><startPage>1</startPage><display>100</display>
<empEvent><areaCd>51</areaCd><area>서울/강원 지역</area><eventNo>1</eventNo><eventNm>2026 영등포구 취업박람회</eventNm><eventTerm>{SOON} ~ {SOON}</eventTerm><startDt>{SOON}</startDt></empEvent>
<empEvent><areaCd>52</areaCd><area>경기/인천 지역</area><eventNo>2</eventNo><eventNm>어린이집 조리사 현장면접</eventNm><eventTerm>{SOON} ~ {SOON}</eventTerm><startDt>{SOON}</startDt></empEvent>
<empEvent><areaCd>53</areaCd><area>부산/경남 지역</area><eventNo>3</eventNo><eventNm>부산 청년 채용박람회</eventNm><eventTerm>{SOON} ~ {SOON}</eventTerm><startDt>{SOON}</startDt></empEvent>
<empEvent><areaCd>51</areaCd><area>서울/강원 지역</area><eventNo>4</eventNo><eventNm>취업박람회 참가 기업 신청 안내</eventNm><eventTerm>{SOON} ~ {SOON}</eventTerm><startDt>{SOON}</startDt></empEvent>
<empEvent><areaCd>52</areaCd><area>경기/인천 지역</area><eventNo>5</eventNo><eventNm>지난 청년 박람회</eventNm><eventTerm>{PAST} ~ {PAST}</eventTerm><startDt>{PAST}</startDt></empEvent>
</empEvList>"""

DETAIL_XML = f"""<empEventDtl><eventNm>2026 영등포구 취업박람회</eventNm>
<eventTerm>{SOON} ~ {SOON} (10:00 ~ 16:00)</eventTerm><eventPlc>영등포아트홀</eventPlc>
<subMatter>현장면접 · 채용설명회 · 이력서 컨설팅</subMatter>
<inqTelNo>02-000-0000</inqTelNo><charger>담당자이름</charger><email>someone@korea.kr</email></empEventDtl>"""


@pytest.fixture
def fake_api(monkeypatch):
    monkeypatch.setenv("WORK24_API_KEY", "secret-key-value")
    calls = []

    def fake_get_xml(url, params):
        calls.append((url, dict(params)))
        if url == work24_events.LIST_URL:
            return ET.fromstring(LIST_XML)
        return ET.fromstring(DETAIL_XML)

    monkeypatch.setattr(work24_events.work24, "_get_xml", fake_get_xml)
    return calls


def test_only_upcoming_capital_area_fairs_for_job_seekers(fake_api):
    kept = work24_events.fetch()

    # 조리사 현장면접(말 없음) · 부산(지역 밖) · 기업 참가 신청 · 지난 행사는 빠진다.
    assert [event["no"] for event in kept] == ["1"]
    details = [c for c in fake_api if c[0] == work24_events.DETAIL_URL]
    assert details == [(work24_events.DETAIL_URL, {"callTp": "D", "eventNo": "1", "areaCd": "51"})]


def test_fields_and_no_contact_details(fake_api):
    normalized = work24_events.normalize(work24_events.fetch()[0])

    assert normalized["opportunity_type"] == "job_event"
    assert normalized["source"] == "work24_event"
    assert normalized["title"] == "2026 영등포구 취업박람회"
    assert normalized["location"] == "영등포아트홀"
    assert normalized["deadline"].date().isoformat() == SOON
    assert normalized["source_url"] == ""
    assert "일시: " in normalized["description"] and "(10:00 ~ 16:00)" in normalized["description"]
    for secret in ("02-000-0000", "담당자이름", "someone@korea.kr"):
        assert secret not in normalized["description"]


def test_regions_are_configurable(fake_api, monkeypatch):
    monkeypatch.setenv("CAREER_OS_WORK24_EVENT_REGIONS", "부산")
    assert [event["no"] for event in work24_events.fetch()] == ["3"]


def test_off_without_a_key(monkeypatch):
    monkeypatch.delenv("WORK24_API_KEY", raising=False)
    assert work24_events.is_available() is False
    with pytest.raises(base.CollectorError):
        work24_events.fetch()


def test_events_are_saved_as_their_own_type(db_session, fake_api):
    result = opportunity_service.collect_from(db_session, work24_events)

    assert result["created"] == 1
    saved = db_session.query(models.Opportunity).filter_by(source="work24_event").one()
    assert saved.opportunity_type == "job_event"
