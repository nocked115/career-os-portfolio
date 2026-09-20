"""데이터 · AI 직무인가 — 2026-09-17 고용24 에서 실제로 들어온 부문들로.

18건 중 10건이 영업 · 마케팅 · 생산이었다. 이 테스트의 예는 전부 그날 받은 공고에서 왔다.
"""

import pytest

from app import models
from app.services import job_fit
from app.services import market as market_service
from app.services import opportunity as opportunity_service


@pytest.mark.parametrize("name, career, job", [
    ("데이터 사이언티스트/데이터 엔지니어", "신입", "상세 모집요강 참조"),
    ("AI/DX 전략", "신입", "상세 모집요강 참조"),
    ("디지털·데이터분석 外", "신입", "상세 모집요강 참조"),
    ("AI 솔루션 개발", "신입", "- AI 솔루션 개발 및 프로젝트 수행"),
    ("IT", "신입", "[AI 자동화 및 데이터 분석] - 데이터 기반 AI 모델 개발 및 자동화 적용"),
    ("IT(5급)", "", "- 경영정보, 빅데이터 시스템 개발 및 운영 등"),
    ("신용분석", "신입", "- Data 분석 기반 영업 기획 및 상품개발 - 채권모형 개발 및 운영·관리"),
])
def test_data_and_ai_sections_are_kept(name, career, job):
    ok, _ = job_fit.judge_section(name, career, job)
    assert ok


@pytest.mark.parametrize("name, career, job", [
    # 설명에 "데이터 분석" 이 있어도 직무 자체가 영업 · 마케팅 · 생산이다.
    ("건강식품/건강기능식품 온라인 영업", "경력", "- 채널별 매출 목표 수립 - 데이터 분석"),
    ("홈쇼핑 마케팅", "신입", "- 데이터 분석 기반 마케팅 액션 설계"),
    ("키녹 신사업 CRM 마케팅(경력)", "경력", "- 고객 데이터 분석 기반 고객군별 CRM 전략 수립"),
    ("뷰티 디바이스 SMT 생산기술", "신입|인턴", "- SMT 공정 운영 - 데이터 분석"),
    # 이름에 Data · AI 가 있어도 하는 일이 다르다.
    ("QC Data Management", "신입|인턴", "- 전자시스템 운영/관리 업무 지원 - 데이터 관리 업무 지원"),
    ("AI Content Creator", "신입", "1. 생성형 AI를 활용한 이미지/영상 제작"),
    ("데이터완전성팀", "경력|신입", "- Audit trail review - 데이터완전성 위험 평가"),
    # 짧은 영문이 다른 낱말에 걸리지 않는다.
    ("경영지원", "신입", "- 마케팅, 회계 등 - 디지털/IT : 빅데이터, AI, 플랫폼 등"),
])
def test_other_jobs_are_left_out(name, career, job):
    ok, why = job_fit.judge_section(name, career, job)
    assert not ok
    assert name in why


def test_career_only_sections_are_left_out():
    ok, why = job_fit.judge_section("데이터 엔지니어", "경력", "- 데이터 파이프라인")
    assert not ok
    assert "경력만" in why

    ok, _ = job_fit.judge_section("데이터 엔지니어", "경력|신입", "- 데이터 파이프라인")
    assert ok


def test_one_fitting_section_keeps_a_big_posting():
    judged = job_fit.judge_sections([
        {"name": "생산", "career": "신입", "job": "- 수율 관리"},
        {"name": "IT", "career": "신입", "job": "- 데이터 기반 AI 모델 개발"},
        {"name": "인사", "career": "신입", "job": "- 채용"},
    ])

    assert judged["fits"]
    assert [section["name"] for section in judged["kept"]] == ["IT"]


def test_sections_are_read_back_from_the_saved_description():
    description = "\n".join([
        "모집 부문: 홈쇼핑 MD · 신입 · 서울 — - 상품 소싱",
        "모집 부문: [일반정규직] AI·디지털 外 — 상세 모집요강 참조",
        "  학력: 대졸",
        "출처: 고용24 공채속보",
    ])

    assert job_fit.parse_sections(description) == [
        {"name": "홈쇼핑 MD", "career": "신입", "job": "- 상품 소싱"},
        {"name": "[일반정규직] AI·디지털 外", "career": "", "job": "상세 모집요강 참조"},
    ]


def _posting(db, title, description, source="work24"):
    opportunity = models.Opportunity(
        opportunity_type="job", title=title, source=source, description=description,
    )
    db.add(opportunity)
    db.flush()
    return opportunity


def test_already_collected_junk_goes_to_the_archive_and_out_of_demand(client, db_session):
    skill = models.Skill(name="Data Analysis", category="data", level=2, aliases="데이터 분석")
    db_session.add(skill)
    sales = _posting(
        db_session, "건강식품 온라인 영업",
        "모집 부문: 건강식품 온라인 영업 · 경력 — - 데이터 분석 기반 매출 관리",
    )
    data = _posting(
        db_session, "신입사원 채용",
        "모집 부문: 데이터 사이언티스트 · 신입 — - 데이터 분석 및 모델링",
    )
    sales.skills.append(skill)
    data.skills.append(skill)
    db_session.commit()

    assert market_service.count_opportunities(db_session) == 2

    result = opportunity_service.review_fit(db_session)

    assert result == {"filtered": 1, "restored": 0}
    db_session.refresh(sales)
    assert "영업" in sales.filtered_reason
    # 뺀 공고는 수요로 세지 않는다.
    assert sales.skills == []
    assert market_service.count_opportunities(db_session) == 1

    matches = {row["opportunity_id"]: row for row in client.get("/opportunities/matches").json()["matches"]}
    assert matches[sales.id]["lane"] == "archived"
    assert matches[sales.id]["archive_reason"] == "직무가 달라 자동으로 뺌"
    assert matches[data.id]["lane"] == "review"

    # 두 번 돌려도 같은 결과.
    assert opportunity_service.review_fit(db_session) == {"filtered": 0, "restored": 0}


def test_keep_anyway_brings_it_back_for_good(client, db_session):
    sales = _posting(db_session, "홈쇼핑 마케팅", "모집 부문: 홈쇼핑 마케팅 · 신입 — - 데이터 분석")
    db_session.commit()
    opportunity_service.review_fit(db_session)

    kept = client.post(f"/opportunities/{sales.id}/keep")

    assert kept.status_code == 200
    assert kept.json()["lane"] == "review"
    opportunity_service.review_fit(db_session)
    db_session.refresh(sales)
    assert sales.filtered_reason == ""


def test_postings_with_an_application_or_from_other_sources_are_not_touched(db_session):
    manual = _posting(db_session, "영업", "모집 부문: 영업 · 신입 — - 판매", source="manual")
    applied = _posting(db_session, "영업", "모집 부문: 영업 · 신입 — - 판매")
    db_session.add(models.Application(opportunity_id=applied.id))
    db_session.commit()

    opportunity_service.review_fit(db_session)

    db_session.refresh(manual)
    db_session.refresh(applied)
    assert manual.filtered_reason == ""
    assert applied.filtered_reason == ""
