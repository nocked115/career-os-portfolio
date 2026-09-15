"""고용24 공채속보 수집원 — 부문으로 고르고, 받은 것만 적고, 키를 흘리지 않는다."""

import urllib.error
import xml.etree.ElementTree as ET

import pytest

from app import models
from app.collectors import base, work24
from app.services import opportunity as opportunity_service


LIST_XML = """<dhsOpenEmpInfoList><total>3</total><startPage>1</startPage><display>100</display>
<dhsOpenEmpInfo><empSeqno>1</empSeqno><empWantedTitle>'26년 하반기 대졸 신입사원 모집</empWantedTitle>
<empBusiNm>테스트전자</empBusiNm><coClcdNm>대기업</coClcdNm><empWantedStdt>20260909</empWantedStdt>
<empWantedEndt>20260927</empWantedEndt><empWantedTypeNm>정규직</empWantedTypeNm>
<empWantedHomepgDetail>https://recruit.example.com/1</empWantedHomepgDetail></dhsOpenEmpInfo>
<dhsOpenEmpInfo><empSeqno>2</empSeqno><empWantedTitle>생산직 채용</empWantedTitle><empBusiNm>테스트중공업</empBusiNm>
<empWantedStdt>20260910</empWantedStdt><empWantedEndt>20260930</empWantedEndt></dhsOpenEmpInfo>
<dhsOpenEmpInfo><empSeqno>3</empSeqno><empWantedTitle>E-MAIL 마케팅 담당</empWantedTitle><empBusiNm>테스트유통</empBusiNm>
<empWantedStdt>20260910</empWantedStdt><empWantedEndt>20260930</empWantedEndt></dhsOpenEmpInfo>
</dhsOpenEmpInfoList>"""

DETAILS = {
    "1": """<dhsOpenEmpInfoDetailRoot><empSeqno>1</empSeqno>
<empSelsList><empSelsListInfo><selsNm>서류전형</selsNm></empSelsListInfo><empSelsListInfo><selsNm>면접전형</selsNm></empSelsListInfo></empSelsList>
<empRecrList>
<empRecrListInfo><empRecrNm>DX</empRecrNm><jobCont>- 데이터 분석 및 머신러닝 모델 개발</jobCont><empWantedCareerNm>신입</empWantedCareerNm><empWantedEduNm>대졸</empWantedEduNm><workRegionNm>수원</workRegionNm></empRecrListInfo>
<empRecrListInfo><empRecrNm>영업</empRecrNm><jobCont>- 국내 영업</jobCont><empWantedCareerNm>신입</empWantedCareerNm><workRegionNm>서울</workRegionNm></empRecrListInfo>
</empRecrList></dhsOpenEmpInfoDetailRoot>""",
    "2": """<dhsOpenEmpInfoDetailRoot><empSeqno>2</empSeqno><empRecrList>
<empRecrListInfo><empRecrNm>생산</empRecrNm><jobCont>- 조립 라인 - 생산 실적 데이터 정리 - AI Tool 활용 보고서</jobCont><empWantedCareerNm>경력무관</empWantedCareerNm></empRecrListInfo>
</empRecrList></dhsOpenEmpInfoDetailRoot>""",
    "3": """<dhsOpenEmpInfoDetailRoot><empSeqno>3</empSeqno><empRecrList>
<empRecrListInfo><empRecrNm>마케팅</empRecrNm><jobCont>- E-MAIL 캠페인</jobCont></empRecrListInfo>
</empRecrList></dhsOpenEmpInfoDetailRoot>""",
}


@pytest.fixture
def fake_api(monkeypatch):
    monkeypatch.setenv("WORK24_API_KEY", "secret-key-value")
    calls = []

    def fake_get_xml(url, params):
        calls.append((url, dict(params)))
        if url == work24.LIST_URL:
            return ET.fromstring(LIST_XML)
        return ET.fromstring(DETAILS[str(params["empSeqno"])])

    monkeypatch.setattr(work24, "_get_xml", fake_get_xml)
    return calls


# --------------------------------
# 켜고 끄기
# --------------------------------

def test_off_without_a_key(monkeypatch):
    monkeypatch.delenv("WORK24_API_KEY", raising=False)
    assert work24.is_available() is False


def test_never_in_the_public_demo(monkeypatch):
    monkeypatch.setenv("WORK24_API_KEY", "k")
    monkeypatch.setenv("CAREER_OS_PUBLIC_DEMO", "1")
    assert work24.is_available() is False


def test_fetch_without_a_key_sends_nothing(monkeypatch):
    monkeypatch.delenv("WORK24_API_KEY", raising=False)
    monkeypatch.setattr(work24, "_get_xml", lambda *a, **k: pytest.fail("외부 호출"))
    with pytest.raises(base.CollectorError):
        work24.fetch()


# --------------------------------
# 고르기 · 옮겨 적기
# --------------------------------

def test_postings_are_kept_by_recruit_section_not_title(fake_api):
    kept = work24.fetch()

    # 제목에는 없지만 DX 부문의 직무 설명에 "데이터 분석 · 머신러닝" 이 있다.
    # 생산직의 "데이터 정리 · AI Tool" 은 직무 설명 속 짧은 말이라 고르지 않는다.
    # E-MAIL 마케팅의 AI 는 단어 경계에 걸리지 않는다.
    assert [item["seqno"] for item in kept] == ["1"]
    assert kept[0]["matched"] == ["데이터 분석", "머신러닝", "DX"]
    assert len([c for c in fake_api if c[0] == work24.DETAIL_URL]) == 3


def test_short_words_count_only_in_titles_and_section_names():
    assert work24._matches("AI 솔루션 개발 부문", work24.section_words()) == ["AI"]
    assert work24._matches("QC Data Management", work24.section_words()) == ["Data"]
    assert work24._matches("- 급여 데이터 관리", work24.keywords()) == []
    assert work24._matches("- 데이터 파이프라인 구축", work24.keywords()) == ["데이터 파이프라인"]


def test_fields_land_where_they_belong(fake_api):
    normalized = work24.normalize(work24.fetch()[0])

    assert normalized["source"] == "work24"
    assert normalized["source_external_id"] == "1"
    assert normalized["title"] == "'26년 하반기 대졸 신입사원 모집"
    assert normalized["organization"] == "테스트전자"
    assert normalized["source_url"] == "https://recruit.example.com/1"
    assert normalized["location"] == "수원, 서울"
    assert normalized["employment_type"] == "정규직"
    assert normalized["deadline"].strftime("%Y-%m-%d") == "2026-09-27"
    assert "모집 부문: DX · 신입 · 수원 — - 데이터 분석 및 머신러닝 모델 개발" in normalized["description"]
    assert "전형: 서류전형 → 면접전형" in normalized["description"]
    assert normalized["description"].endswith("출처: 고용24 공채속보")


def test_missing_fields_stay_empty_not_guessed():
    normalized = work24.normalize({"seqno": "9", "title": "공고", "sections": [], "matched": ["AI"]})

    assert normalized["organization"] == ""
    assert normalized["location"] == ""
    assert normalized["deadline"] is None
    assert normalized["source_url"] == ""


def test_detail_limit_caps_calls(fake_api, monkeypatch):
    monkeypatch.setenv("CAREER_OS_WORK24_MAX_DETAILS", "1")
    work24.fetch()
    assert len([c for c in fake_api if c[0] == work24.DETAIL_URL]) == 1


def test_network_errors_do_not_leak_the_key(monkeypatch):
    monkeypatch.setenv("WORK24_API_KEY", "secret-key-value")

    def boom(*args, **kwargs):
        raise urllib.error.URLError("https://www.work24.go.kr/?authKey=secret-key-value")

    monkeypatch.setattr(work24.urllib.request, "urlopen", boom)

    with pytest.raises(base.CollectorError) as caught:
        work24.fetch()

    assert "secret-key-value" not in str(caught.value)


def test_collected_postings_are_saved_and_linked(db_session, fake_api):
    db_session.add(models.Skill(name="Machine Learning", category="ai", level=2, aliases="머신러닝"))
    db_session.commit()

    result = opportunity_service.collect_from(db_session, work24)

    assert (result["status"], result["created"]) == ("completed", 1)
    saved = db_session.query(models.Opportunity).filter_by(source="work24").one()
    assert [skill.name for skill in saved.skills] == ["Machine Learning"]

    again = opportunity_service.collect_from(db_session, work24)
    assert (again["created"], again["updated"]) == (0, 1)
