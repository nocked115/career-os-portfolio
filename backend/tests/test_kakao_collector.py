"""카카오 채용 — 문서화된 API 가 아니라서, 막히면 막혔다고 말해야 한다."""

import json
import urllib.error

import pytest

from app.collectors import base, kakao


PAGE = {
    "totalJobCount": 3,
    "totalPage": 1,
    "jobList": [
        {
            "realId": "S-1",
            "jobOfferTitle": "[공동체] 카카오페이 데이터 엔지니어 - 데이터 플랫폼",
            "companyName": "카카오페이",
            "locationName": "판교",
            "employeeTypeName": "정규직",
            "introduction": "<p>데이터 파이프라인을 만듭니다.</p>",
            "workContentDesc": "<p>머신러닝 모델 개발과 데이터 엔지니어 업무</p>",
            "qualification": "<p>Python, SQL</p>",
            "skillSetList": [{"name": "Python"}],
            "endDate": None,
        },
        {
            "realId": "S-2",
            "jobOfferTitle": "Data Scientist (경력)",
            "companyName": "카카오",
            "introduction": "<p>머신러닝 모델 개발 · 추천시스템</p>",
        },
        {
            "realId": "S-3",
            "jobOfferTitle": "iOS 개발자",
            "companyName": "카카오",
            "introduction": "<p>앱을 만듭니다. AI 를 활용합니다.</p>",
        },
    ],
}


@pytest.fixture
def board(monkeypatch):
    monkeypatch.setattr(kakao, "robots_allows", lambda url: True)
    monkeypatch.setattr(kakao, "_get_json", lambda url: PAGE)


def test_only_data_jobs_a_new_grad_can_apply_to(board):
    kept = kakao.fetch()

    # 경력 전용(Data Scientist (경력))과 iOS 는 뺀다.
    assert [job["id"] for job in kept] == ["S-1"]


def test_robots_blocking_us_stops_collection(monkeypatch):
    monkeypatch.setattr(kakao, "robots_allows", lambda url: False)
    monkeypatch.setattr(kakao, "_get_json", lambda url: pytest.fail("robots 를 무시했다"))

    with pytest.raises(base.CollectorError) as caught:
        kakao.fetch()

    assert "robots" in str(caught.value)


def test_a_block_is_reported_not_swallowed(monkeypatch):
    """403 이 와도 "0건 수집" 으로 조용히 넘어가지 않는다."""
    monkeypatch.setattr(kakao, "robots_allows", lambda url: True)

    def blocked(url):
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(kakao, "_get_json", kakao._get_json)
    monkeypatch.setattr(kakao.urllib.request, "urlopen", lambda *a, **k: blocked(""))

    with pytest.raises(base.CollectorError) as caught:
        kakao.fetch()

    assert "403" in str(caught.value)


def test_a_changed_response_is_reported(monkeypatch):
    monkeypatch.setattr(kakao, "robots_allows", lambda url: True)

    def not_json(url):
        raise json.JSONDecodeError("x", "y", 0)

    monkeypatch.setattr(kakao, "_get_json", lambda url: not_json(url))

    with pytest.raises(json.JSONDecodeError):
        kakao.fetch()


def test_fields_land_where_they_belong(board):
    normalized = kakao.normalize(kakao.fetch()[0])

    assert normalized["source"] == "kakao"
    assert normalized["source_external_id"] == "S-1"
    assert normalized["organization"] == "카카오페이"
    assert normalized["source_url"] == "https://careers.kakao.com/jobs/S-1"
    assert normalized["location"] == "판교"
    assert "데이터 파이프라인" in normalized["description"]
    assert normalized["description"].endswith("출처: 카카오 채용")
