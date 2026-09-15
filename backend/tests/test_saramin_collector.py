"""사람인 수집원.

네트워크는 부르지 않는다. 문서에 적힌 응답 형태로 fixture 를 만든다
(https://oapi.saramin.co.kr/guide/job-search).
"""

from datetime import datetime

import pytest

from app import models
from app.collectors import base, saramin
from app.services import opportunity as opportunity_service


def _job(**over):
    job = {
        "url": "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=1",
        "active": 1,
        "id": "49000001",
        "company": {"detail": {"href": "https://x", "name": "어떤데이터"}},
        "position": {
            "title": "데이터 분석가 (신입)",
            "location": {"code": "101000", "name": "서울 &gt; 강남구"},
            "job-type": {"code": "1", "name": "정규직"},
            "industry": {"code": "301", "name": "솔루션·SI·ERP·CRM"},
            "job-mid-code": {"code": "2", "name": "IT개발·데이터"},
            "job-code": {"code": "84", "name": "데이터분석가"},
            "experience-level": {"code": 1, "min": 0, "max": 0, "name": "신입"},
            "required-education-level": {"code": "8", "name": "대학교졸업(4년)"},
        },
        "keyword": "머신러닝, SQL, Python",
        "posting-timestamp": "1757900000",
        "expiration-timestamp": "1760000000",
        "close-type": {"code": "1", "name": "접수마감일"},
    }
    job.update(over)
    return job


# --- 켜지는 조건 ---

def test_off_without_a_key(monkeypatch):
    monkeypatch.delenv("SARAMIN_API_KEY", raising=False)
    assert saramin.is_available() is False


def test_an_empty_key_is_not_a_key(monkeypatch):
    """.env 에 SARAMIN_API_KEY= 만 있고 값이 비어 있었다. 실제로 그랬다."""
    monkeypatch.setenv("SARAMIN_API_KEY", "   ")
    assert saramin.is_available() is False


def test_on_with_a_key(monkeypatch):
    monkeypatch.setenv("SARAMIN_API_KEY", "k")
    monkeypatch.delenv("CAREER_OS_PUBLIC_DEMO", raising=False)
    assert saramin.is_available() is True


def test_never_in_the_public_demo(monkeypatch):
    """약관이 재배포를 금지한다. 공개 데모에 사람인 공고를 싣지 않는다."""
    monkeypatch.setenv("SARAMIN_API_KEY", "k")
    monkeypatch.setenv("CAREER_OS_PUBLIC_DEMO", "1")
    assert saramin.is_available() is False


# --- 정규화 ---

def test_fields_land_where_they_belong():
    n = saramin.normalize(_job())

    assert n["source"] == "saramin"
    assert n["source_external_id"] == "49000001"
    assert n["title"] == "데이터 분석가 (신입)"
    assert n["organization"] == "어떤데이터"
    assert n["employment_type"] == "정규직"
    assert n["source_url"].startswith("https://www.saramin.co.kr/")
    assert "출처: 사람인" in n["description"]


def test_skill_words_reach_the_description():
    """본문이 없으니 키워드·직무명이 스킬 추출의 재료다."""
    n = saramin.normalize(_job())

    assert "머신러닝" in n["description"]
    assert "데이터분석가" in n["description"]


def test_a_real_deadline_is_kept():
    n = saramin.normalize(_job())
    assert n["deadline"] == datetime.fromtimestamp(1760000000)


@pytest.mark.parametrize("code", ["2", "3", "4"])
def test_rolling_postings_get_no_deadline(code):
    """채용 시·상시·수시에 만료 시각을 마감으로 넣으면 가짜 D-day 가 뜬다."""
    n = saramin.normalize(_job(**{"close-type": {"code": code, "name": "상시"}}))
    assert n["deadline"] is None


def test_missing_fields_stay_empty_not_guessed():
    n = saramin.normalize({
        "id": "1", "position": {"title": "제목만 있음"},
        "close-type": {"code": "1"},
    })

    assert n["organization"] == ""
    assert n["deadline"] is None
    assert "키워드: " not in n["description"]


def test_no_title_is_rejected():
    with pytest.raises(base.CollectorError):
        saramin.normalize({"id": "1", "position": {}})


# --- 수집 ---

def test_fetch_merges_keywords_and_drops_closed(monkeypatch):
    monkeypatch.setenv("SARAMIN_API_KEY", "k")
    monkeypatch.setenv("CAREER_OS_SARAMIN_KEYWORDS", "데이터,머신러닝")

    calls = []

    def fake_get(params):
        calls.append(params["keywords"])
        return {"jobs": {"job": [
            _job(id="1"),
            _job(id="2", active=0),   # 마감됨
        ]}}

    monkeypatch.setattr(saramin, "_get", fake_get)

    jobs = saramin.fetch()

    assert calls == ["데이터", "머신러닝"]   # 키워드마다 1회
    assert [j["id"] for j in jobs] == ["1"]  # 겹친 것 1개, 마감 제외


def test_api_error_codes_become_collector_errors(monkeypatch):
    monkeypatch.setenv("SARAMIN_API_KEY", "secret-value")

    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"result": {"code": 2, "message": "invalid"}}'

    monkeypatch.setattr(saramin.urllib.request, "urlopen", lambda *a, **k: Resp())

    with pytest.raises(base.CollectorError) as caught:
        saramin._get({"keywords": "x"})

    assert "유효하지" in str(caught.value)
    assert "secret-value" not in str(caught.value)


def test_network_errors_do_not_leak_the_key(monkeypatch):
    """오류 메시지에 URL 이 섞이면 키가 로그에 남는다."""
    monkeypatch.setenv("SARAMIN_API_KEY", "secret-value")

    def boom(*a, **k):
        raise saramin.urllib.error.URLError(
            "https://oapi.saramin.co.kr/job-search?access-key=secret-value"
        )

    monkeypatch.setattr(saramin.urllib.request, "urlopen", boom)

    with pytest.raises(base.CollectorError) as caught:
        saramin._get({"keywords": "x"})

    assert "secret-value" not in str(caught.value)


def test_collected_postings_are_saved_and_linked(db_session, monkeypatch):
    db_session.add(models.Skill(name="Machine Learning", category="ai",
                                aliases="머신러닝, ML"))
    db_session.commit()

    monkeypatch.setattr(saramin, "fetch", lambda: [_job()])

    result = opportunity_service.collect_from(db_session, saramin)

    assert result["created"] == 1

    saved = db_session.query(models.Opportunity).one()
    assert saved.source == "saramin"
    assert [s.name for s in saved.skills] == ["Machine Learning"]

    # 다시 모아도 같은 공고가 둘이 되지 않는다
    result = opportunity_service.collect_from(db_session, saramin)
    assert result["created"] == 0
    assert db_session.query(models.Opportunity).count() == 1


def test_match_payload_names_the_source(client, db_session):
    """약관의 출처 표시. 화면이 이 값으로 "사람인" 을 붙인다."""
    db_session.add(models.Opportunity(
        title="t", organization="o", opportunity_type="job", source="saramin",
    ))
    db_session.commit()

    match = client.get("/opportunities/matches").json()["matches"][0]
    assert match["source"] == "saramin"


def test_fetch_without_a_key_sends_nothing(monkeypatch):
    """키가 없으면 요청 자체를 보내지 않는다. 테스트에서 실제로 나갔었다."""
    monkeypatch.delenv("SARAMIN_API_KEY", raising=False)

    def must_not_call(*a, **k):
        raise AssertionError("네트워크 요청이 나갔습니다")

    monkeypatch.setattr(saramin.urllib.request, "urlopen", must_not_call)

    with pytest.raises(base.CollectorError):
        saramin.fetch()
