"""한눈에 보기와 회고 — 숫자는 분모와 함께, 제안은 기록이 있을 때만."""

from datetime import date, timedelta

from app import models
from app.services import overview as overview_service
from app.services import review as review_service


THURSDAY = date(2026, 9, 17)


def _task(db, day, status, title="할 일", task_type="learning_step", carried_from=None):
    db.add(models.DailyPlanTask(
        plan_date=day, position=0, task_type=task_type, title=title,
        minutes=30, reason="테스트", status=status, carried_from=carried_from,
    ))


# --------------------------------
# 한눈에 보기
# --------------------------------

def test_the_overview_route_works_on_an_empty_install(client):
    body = client.get("/overview").json()

    assert body["next_action"] is None
    assert body["week"]["rate"] is None
    assert body["learning"]["steps_total"] == 0


def test_the_week_rate_counts_only_days_that_are_over(db_session):
    monday = THURSDAY - timedelta(days=3)
    _task(db_session, monday, "done")
    _task(db_session, monday + timedelta(days=1), "done")
    _task(db_session, monday + timedelta(days=1), "skipped")
    _task(db_session, monday + timedelta(days=2), "planned")   # 어제 못 한 것
    _task(db_session, THURSDAY, "planned")                     # 오늘 아직 안 한 것
    _task(db_session, monday - timedelta(days=1), "done")      # 지난주
    db_session.commit()

    week = overview_service.build_overview(db_session, THURSDAY)["week"]

    assert (week["done"], week["skipped"], week["missed"], week["pending_today"]) == (2, 1, 1, 1)
    assert week["decided"] == 4
    assert week["rate"] == 50


def test_the_overview_points_at_the_first_planned_task(db_session):
    _task(db_session, THURSDAY, "done", title="끝낸 것")
    _task(db_session, THURSDAY, "planned", title="다음 할 것")
    db_session.commit()

    action = overview_service.build_overview(db_session, THURSDAY)["next_action"]

    assert action["title"] == "다음 할 것"
    assert action["area"] == "학습"


# --------------------------------
# 회고 — 계획 대비 실행 · 미룬 일 · 다음 달
# --------------------------------

def test_execution_is_counted_against_what_was_planned(db_session):
    for day in range(1, 7):
        _task(db_session, date(2026, 9, day), "done" if day <= 2 else "skipped")
    db_session.commit()

    review = review_service.build_review(db_session, 2026, 9, today=date(2026, 9, 30))

    assert review["execution"]["decided"] == 6
    assert review["execution"]["rate"] == 33
    assert review["next_month"][0]["title"] == "하루 계획을 줄여 보세요"
    assert "6개 중 2개" in review["next_month"][0]["evidence"]


def test_too_few_records_do_not_trigger_a_lecture(db_session):
    _task(db_session, date(2026, 9, 1), "skipped")
    _task(db_session, date(2026, 9, 2), "skipped")
    db_session.commit()

    review = review_service.build_review(db_session, 2026, 9, today=date(2026, 9, 30))

    assert review["execution"]["rate"] == 0
    assert review["next_month"] == []


def test_repeatedly_postponed_work_is_named(db_session):
    for day in (3, 4, 5):
        _task(db_session, date(2026, 9, day), "planned", title="FastAPI 배포",
              carried_from=date(2026, 9, 2))
    _task(db_session, date(2026, 9, 5), "done", title="다른 일")
    db_session.commit()

    review = review_service.build_review(db_session, 2026, 9, today=date(2026, 9, 30))

    assert review["postponed"][0] == {
        "title": "FastAPI 배포", "times": 3, "first_planned": "2026-09-02",
    }
    assert any("FastAPI 배포" in item["title"] for item in review["next_month"])


def test_a_month_without_plans_asks_for_a_plan(db_session):
    review = review_service.build_review(db_session, 2026, 8, today=date(2026, 9, 30))

    assert review["execution"]["planned"] == 0
    assert review["next_month"][0]["route"] == "today"


# --------------------------------
# 홈 — 오늘 카드는 개수가 아니라 첫 할 일을 보인다
# --------------------------------

def test_the_universe_today_card_names_the_first_planned_task(db_session):
    from app.services import universe as universe_service

    _task(db_session, THURSDAY, "done", title="끝낸 것")
    _task(db_session, THURSDAY, "planned", title="SQL 윈도우 함수")
    db_session.commit()

    today = universe_service.build_universe(db_session, THURSDAY)["today"]

    assert today["first_task"] == {"title": "SQL 윈도우 함수", "minutes": 30, "area": "학습"}
