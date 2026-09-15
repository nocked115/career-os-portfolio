"""붙여넣은 공고 글에서 칸을 채운다 — 못 찾으면 비워 둔다.

앱은 공고 사이트를 열지 않는다. 사람이 읽은 글만 다룬다.
"""

from datetime import date, datetime, timedelta

from app import models
from app.services import posting_parser as parser


TODAY = date(2026, 9, 10)

POSTING = """한빛전자 AI부문
2026년 하반기 신입사원 채용
인공지능 (AI부문)

수행업무
머신러닝, 자연어 처리, 영상 인식 소프트웨어 개발

지원자격
□ 학계 경력 1년 이상 또는 석사 학위 소지자
□ 영어회화 최소등급: IL(OPIc) 또는 110점 이상(토익스피킹)

전형절차
서류전형 > 직무적성검사 > 면접

접수기간: 2026.09.08(월) ~ 2026.09.15(월) 23:59
근무지: 수원
입사일: 2027년 1월 4일
"""


def _parse(db_session, text=POSTING, today=TODAY):
    return parser.parse_posting(db_session, text, "https://example.com/job", today=today)


def test_the_deadline_is_the_end_of_the_application_period(db_session):
    deadline = _parse(db_session)["deadline"]

    assert deadline["value"] == "2026-09-15T23:59"
    assert "접수기간" in deadline["evidence"]
    assert deadline["note"] is None


def test_an_unrelated_date_is_not_taken_as_the_deadline(db_session):
    """입사일은 마감이 아니다. 마감 단서가 있는 줄의 날짜만 본다."""
    text = "데이터 분석가 채용\n입사일: 2027년 1월 4일\n"

    deadline = _parse(db_session, text)["deadline"]

    assert deadline["value"] is None
    assert deadline["found"] is False


def test_a_rolling_posting_leaves_the_deadline_empty(db_session):
    deadline = _parse(db_session, "AI 엔지니어 채용\n마감: 상시채용\n")["deadline"]

    assert deadline["value"] is None
    assert deadline["rolling"] is True


def test_a_date_without_a_year_says_which_year_it_assumed(db_session):
    deadline = _parse(db_session, "인턴 모집\n서류 마감 10월 2일\n")["deadline"]

    assert deadline["value"] == "2026-10-02T23:59"
    assert "2026년으로 봤어요" in deadline["note"]


def test_requirement_lines_are_flagged_not_judged(db_session):
    flags = _parse(db_session)["requirement_flags"]
    kinds = {flag["kind"] for flag in flags}

    assert {"career", "degree", "language"} <= kinds
    assert any("학계 경력 1년 이상" in flag["line"] for flag in flags)


def test_qualifications_stop_at_the_next_section(db_session):
    qualifications = _parse(db_session)["qualifications"]

    assert len(qualifications) == 2
    assert not any("서류전형" in line for line in qualifications)


def test_registered_skills_are_found(db_session):
    db_session.add(models.Skill(name="Machine Learning", category="ai", aliases="머신러닝"))
    db_session.commit()

    skills = _parse(db_session)["skills"]

    assert [skill["name"] for skill in skills] == ["Machine Learning"]


def test_a_missing_company_stays_empty(db_session):
    """"한빛전자 AI부문" 을 회사로 짐작하지 않는다. 확실한 표기가 없으면 비운다."""
    result = _parse(db_session)

    assert result["organization"]["value"] == ""
    assert "채용" in result["title"]["value"]
    assert result["location"]["value"] == "수원"


def test_a_labeled_company_is_read(db_session):
    result = _parse(db_session, "회사명: ㈜에이브랩스\n데이터 분석 (Data Scientist) 채용\n")

    assert result["organization"]["value"] == "㈜에이브랩스"


def test_parsing_does_not_save_anything(client):
    response = client.post("/opportunities/parse", json={"text": POSTING, "url": ""})

    assert response.status_code == 200
    assert client.get("/opportunities").json() == []


def test_matches_carry_status_application_and_flags(client):
    posting = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "인공지능 (AI부문)",
            "source": "manual",
            "description": POSTING,
        },
    ).json()
    application = client.post("/applications", json={"opportunity_id": posting["id"]}).json()

    match = client.get("/opportunities/matches").json()["matches"][0]

    assert match["status"] == "interested"
    assert match["application"] == {"id": application["id"], "status": "interested"}
    assert any(flag["kind"] == "career" for flag in match["requirement_flags"])


def test_a_held_posting_leaves_the_deadline_strip(client):
    """보류한 공고가 Today 마감 띠에 계속 뜨면 보류가 아니다."""
    tomorrow = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
    posting = client.post(
        "/opportunities",
        json={"opportunity_type": "job", "title": "보류할 공고", "source": "manual", "deadline": tomorrow},
    ).json()

    assert client.get("/today/deadlines").json()["deadlines"]

    client.patch(f"/opportunities/{posting['id']}", json={"status": "on_hold"})

    assert client.get("/today/deadlines").json()["deadlines"] == []
