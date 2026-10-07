"""기업 채용 보드(Greenhouse 공개 API) — 키 없이 열리는 공식 출처.

사람인 API 가 반려되고 잡코리아 · 원티드에 공개 API 가 없는 상황에서, 기업이 스스로
공개한 보드가 남은 길이었다. 예시는 2026-09-20 에 실제로 받은 응답에서 왔다.
"""

import pytest

from app import models
from app.collectors import greenhouse
from app.services import opportunity as opportunity_service


BOARD = {
    "jobs": [
        {
            "id": 1,
            "title": "Software Engineer, Backend (신입) - 피드 (ML Data Platform)",
            "company_name": "당근마켓",
            "location": {"name": "SEOUL"},
            "offices": [{"name": "서울"}],
            "departments": [{"name": "Engineering"}],
            "absolute_url": "https://about.daangn.com?gh_jid=1",
            "content": "<p>추천시스템과 머신러닝 파이프라인을 만듭니다. 모델 개발 경험이 있으면 좋아요.</p>",
        },
        {
            "id": 2,
            "title": "Software Engineer, Android",
            "company_name": "당근마켓",
            "location": {"name": "SEOUL"},
            "absolute_url": "https://about.daangn.com?gh_jid=2",
            # 회사 소개에 AI 가 한 번 스친다 — 그것만으로는 데이터 직무가 아니다.
            "content": "<p>당근은 AI 를 활용하는 회사입니다. 안드로이드 앱을 만듭니다.</p>",
        },
        {
            "id": 3,
            "title": "Machine Learning Engineer (10년 이상)",
            "company_name": "당근마켓",
            "location": {"name": "SEOUL"},
            "absolute_url": "https://about.daangn.com?gh_jid=3",
            "content": "<p>머신러닝 모델 개발을 이끕니다.</p>",
        },
        {
            "id": 4,
            "title": "Machine Learning Engineer",
            "company_name": "당근마켓",
            "location": {"name": "San Francisco"},
            "absolute_url": "https://about.daangn.com?gh_jid=4",
            "content": "<p>머신러닝 모델 개발 · 추천시스템</p>",
        },
    ]
}


@pytest.fixture
def board(monkeypatch):
    monkeypatch.setenv("CAREER_OS_GREENHOUSE_BOARDS", "daangn")
    monkeypatch.setattr(greenhouse, "_get_json", lambda url: BOARD)


def test_only_korean_junior_data_jobs_are_kept(board):
    kept = greenhouse.fetch()

    assert [job["id"] for job in kept] == [1]


def test_a_key_is_not_needed_but_the_public_demo_is_off(board, monkeypatch):
    assert greenhouse.is_available() is True

    monkeypatch.setenv("CAREER_OS_PUBLIC_DEMO", "1")
    assert greenhouse.is_available() is False


def test_boards_are_configurable(monkeypatch):
    monkeypatch.setenv("CAREER_OS_GREENHOUSE_BOARDS", "daangn, coupang ")
    assert greenhouse.boards() == ["daangn", "coupang"]


def test_fields_land_where_they_belong(board):
    normalized = greenhouse.normalize(greenhouse.fetch()[0])

    assert normalized["source"] == "greenhouse"
    assert normalized["source_external_id"] == "1"
    assert normalized["organization"] == "당근마켓"
    assert normalized["location"] == "SEOUL"
    assert normalized["source_url"] == "https://about.daangn.com?gh_jid=1"
    # 본문이 들어와야 스킬이 붙는다. 마감은 없으면 비운다 — 상시 채용이 많다.
    assert "머신러닝" in normalized["description"]
    assert normalized["description"].endswith("출처: 기업 채용 보드(Greenhouse 공개 API)")
    assert normalized["deadline"] is None


def test_collected_postings_are_saved_and_linked(client, db_session, board):
    db_session.add(models.Skill(name="Machine Learning", category="ai", level=1, aliases="머신러닝"))
    db_session.commit()

    result = opportunity_service.collect_from(db_session, greenhouse)

    assert (result["status"], result["created"]) == ("completed", 1)
    saved = db_session.query(models.Opportunity).filter_by(source="greenhouse").one()
    assert [skill.name for skill in saved.skills] == ["Machine Learning"]
