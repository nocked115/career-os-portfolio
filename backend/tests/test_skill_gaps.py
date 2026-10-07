"""공고에 적힌 도구 중 내 목록에 없는 것.

수요는 등록된 스킬만 센다. 그래서 목록이 닫혀 있으면 앱은 모르는 도구를
영원히 모른다 — 분모를 아무리 고쳐도 순위가 안 바뀌던 진짜 이유다.
"""

from datetime import date, timedelta

from app import models
from app.services import vocabulary


def _skill(db, name):
    db.add(models.Skill(name=name, category="data", level=0))
    db.commit()


def _posting(db, title, description="", opportunity_type="job"):
    db.add(models.Opportunity(
        opportunity_type=opportunity_type,
        title=title,
        description=description,
        source="test",
        deadline=date.today() + timedelta(days=30),
    ))
    db.commit()


def test_a_tool_in_the_postings_but_not_in_my_skills_is_reported(db_session):
    for i in range(3):
        _posting(db_session, f"데이터 엔지니어 {i}", "Airflow 로 데이터 파이프라인을 만듭니다.")

    result = vocabulary.scan(db_session)
    names = {item["name"] for item in result["missing"]}

    assert "Airflow" in names
    assert "ETL · 데이터 파이프라인" in names

    airflow = next(i for i in result["missing"] if i["name"] == "Airflow")
    assert airflow["count"] == 3
    assert airflow["percentage"] == 100


def test_a_tool_i_already_have_is_not_reported_as_missing(db_session):
    _skill(db_session, "Airflow")
    for i in range(3):
        _posting(db_session, f"공고 {i}", "Airflow 경험자 우대")

    result = vocabulary.scan(db_session)

    assert "Airflow" not in {item["name"] for item in result["missing"]}


def test_one_or_two_mentions_are_not_a_market_signal(db_session):
    """한두 건은 그 회사 사정이지 시장이 아니다."""
    _posting(db_session, "공고", "Snowflake 를 씁니다")
    _posting(db_session, "공고2", "Snowflake 경험")

    result = vocabulary.scan(db_session)

    assert "Snowflake" not in {item["name"] for item in result["missing"]}


def test_korean_spelling_is_counted(db_session):
    """영문만 찾으면 '통계' 라고만 쓴 공고를 놓친다 — 실제로 14건을 놓치고 있었다."""
    for i in range(3):
        _posting(db_session, f"공고 {i}", "통계 분석 경험이 필요합니다.")

    result = vocabulary.scan(db_session)
    stats = next(i for i in result["found"] if i["name"] == "Statistics")

    assert stats["count"] == 3


def test_a_skill_no_posting_asks_for_is_reported(db_session):
    """빼라는 말이 아니라, 왜 올려뒀는지 한 번 보라는 뜻이다."""
    _skill(db_session, "Azure")
    _posting(db_session, "공고", "AWS 를 씁니다")

    assert "Azure" in vocabulary.scan(db_session)["unused"]


def test_job_fairs_are_not_scanned(db_session):
    """수요 모집단과 같아야 % 가 같은 뜻이 된다."""
    _posting(db_session, "진짜 공고", "Airflow")
    for i in range(5):
        _posting(db_session, f"일자리 박람회 {i}", "Airflow", opportunity_type="job_event")

    assert vocabulary.scan(db_session)["scanned"] == 1


def test_endpoint(client):
    body = client.get("/analytics/skill-gaps").json()

    assert "missing" in body
    assert "unused" in body
    assert "scanned" in body
