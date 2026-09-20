"""기간 회고.

하루치로는 아무것도 안 보인다. 한 달을 모아야 "이걸 배웠다" 가 된다.
"""

from datetime import date, datetime

import pytest

from app import models
from app.services import review as review_service


@pytest.fixture
def month(db_session):
    """9월에 실제로 한 일들. 8월과 10월 것도 섞어 넣는다."""
    skill = models.Skill(name="Machine Learning", category="ai")
    other = models.Skill(name="SQL", category="data")
    db_session.add_all([skill, other])
    db_session.flush()

    book = models.LearningResource(
        title="핸즈온 머신러닝", resource_type="book",
        ownership="owned", skill_id=skill.id,
    )
    db_session.add(book)
    db_session.flush()

    def segment(position, label, completed):
        return models.LearningResourceSegment(
            learning_resource_id=book.id, position=position, label=label,
            estimated_minutes=45, status="completed",
            completed_at=completed,
        )

    db_session.add_all([
        segment(0, "1장", datetime(2026, 9, 3, 21, 0)),
        segment(1, "2장", datetime(2026, 9, 11, 20, 0)),
        # 경계 — 마지막 날 밤도 9월이다
        segment(2, "3장", datetime(2026, 9, 30, 23, 30)),
        # 다른 달 — 세면 안 된다
        segment(3, "4장", datetime(2026, 8, 31, 23, 30)),
        segment(4, "5장", datetime(2026, 10, 1, 0, 30)),
        # 안 끝낸 것
        models.LearningResourceSegment(
            learning_resource_id=book.id, position=5, label="6장",
            estimated_minutes=45,
        ),
    ])

    db_session.add(models.DailyPlanTask(
        plan_date=date(2026, 9, 3), position=0, task_type="resource",
        title="핸즈온 머신러닝 — 1장", minutes=45, reason="테스트",
        status="done", completed_at=datetime(2026, 9, 3, 21, 0),
        learning_resource_id=book.id,
    ))

    db_session.add(models.Experience(
        experience_type="project", title="9월에 정리한 경험",
        created_at=datetime(2026, 9, 20),
    ))

    db_session.commit()

    return skill


def test_it_counts_only_that_month(db_session, month):
    r = review_service.build_review(db_session, 2026, 9)

    assert r["learning"]["segments_done"] == 3
    assert r["period"]["label"] == "2026년 9월"


def test_the_last_night_of_the_month_still_counts(db_session, month):
    """9월 30일 23:30 은 9월이다. 경계에서 하루가 사라지면 안 된다."""
    september = review_service.build_review(db_session, 2026, 9)
    october = review_service.build_review(db_session, 2026, 10)

    titles = " ".join(item["title"] for item in september["done"])

    assert "3장" in titles
    assert october["learning"]["segments_done"] == 1  # 10월 1일 것


def test_unfinished_work_is_not_counted(db_session, month):
    """계획한 것이 아니라 끝낸 것을 센다."""
    r = review_service.build_review(db_session, 2026, 9)

    titles = " ".join(item["title"] for item in r["done"])

    assert "6장" not in titles


def test_it_groups_by_skill(db_session, month):
    """45분 공부했다 보다 어느 스킬에 썼는지가 쌓인 것을 말해준다."""
    r = review_service.build_review(db_session, 2026, 9)

    top = r["learning"]["by_skill"][0]

    assert top["skill"] == "Machine Learning"
    assert top["segments"] == 3
    assert top["minutes"] == 45


def test_evidence_and_market_are_counted(db_session, month):
    r = review_service.build_review(db_session, 2026, 9)

    assert r["evidence"]["experiences"] == 1
    assert r["market"]["applications_sent"] == 0


def test_an_empty_month_says_zero(db_session, month):
    """비어 있다는 것도 정확한 상태다. 0 은 0 이다."""
    r = review_service.build_review(db_session, 2026, 7)

    assert r["learning"]["segments_done"] == 0
    assert r["learning"]["by_skill"] == []
    assert r["done"] == []


def test_it_says_what_it_cannot_count(db_session, month):
    """projects 에는 시각이 없다. 지어내지 않는다.

    스킬 레벨은 skill_level_events 가 생기면서 셀 수 있게 됐다
    (test_skill_level.py).
    """
    r = review_service.build_review(db_session, 2026, 9)

    assert "project_completion_date" in r["not_tracked"]
    assert "skill_level_history" not in r["not_tracked"]


def test_the_trend_walks_backwards_without_breaking_the_year(db_session):
    """1월에서 한 달 뒤로 가면 작년 12월이다."""
    months = review_service.recent_months(
        db_session, count=3, today=date(2026, 1, 15)
    )

    labels = [m["period"]["label"] for m in months]

    assert labels == ["2026년 1월", "2025년 12월", "2025년 11월"]


def test_endpoint_defaults_to_this_month(client, db_session, month):
    body = client.get("/analytics/review").json()

    today = date.today()

    assert body["period"]["year"] == today.year
    assert body["period"]["month"] == today.month


def test_endpoint_rejects_half_a_date(client):
    assert client.get("/analytics/review?year=2026").status_code == 422
    assert client.get("/analytics/review?month=9").status_code == 422


def test_a_month_also_records_what_was_dropped(client):
    """할 게 많다는 느낌은 버린 것을 안 적어서 생긴다 — 덜어낸 판단도 남긴다."""
    saved = client.put("/analytics/review/reflection?year=2026&month=9", json={
        "rating": 4,
        "went_well": "코테를 매일 풀었다",
        "to_improve": "",
        "next_focus": "공고 소스 늘리기",
        "dropped": "데이터 엔지니어링 책은 이번 학기에 안 본다",
    }).json()

    assert saved["dropped"] == "데이터 엔지니어링 책은 이번 학기에 안 본다"

    review = client.get("/analytics/review?year=2026&month=9").json()
    assert review["reflection"]["dropped"] == "데이터 엔지니어링 책은 이번 학기에 안 본다"
