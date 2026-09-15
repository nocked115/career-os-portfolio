"""Calendar — 오늘 실제로 몇 분이 비었는가.

학교 시간표를 가져오지 않는다. 직접 넣는다.
"""

from datetime import date, datetime, timedelta

from app import models
from app.services import today as today_service


# "오늘" 을 보는 테스트는 오늘 요일에 일정을 걸어야 한다.
# 월요일로 고정해두면 월요일에만 통과하는 테스트가 된다.
TODAY_WEEKDAY = date.today().weekday()


def _block(client, **kw):
    payload = {
        "title": "수업",
        "kind": "class",
        "weekday": 0,
        "start_minute": 600,
        "end_minute": 720,
    }
    payload.update(kw)
    return client.post("/calendar/blocks", json=payload)


def test_a_block_repeats_weekly_or_happens_once_but_not_both(client):
    """둘 다 비면 언제인지 알 수 없고, 둘 다 차면 언제인지 모호하다."""
    neither = client.post(
        "/calendar/blocks",
        json={
            "title": "수업",
            "start_minute": 600,
            "end_minute": 720,
        },
    )
    assert neither.status_code == 422

    both = _block(client, weekday=0, date="2026-09-07")
    assert both.status_code == 422


def test_end_must_come_after_start(client):
    assert _block(client, start_minute=720, end_minute=600).status_code == 422
    assert _block(client, start_minute=600, end_minute=600).status_code == 422


def test_overlapping_blocks_are_counted_once(client):
    """수업과 알바가 겹치면 두 번 빼게 된다.

    그러면 비어 있는 시간이 실제보다 적게 나온다.
    """
    _block(client, title="자료구조", start_minute=600, end_minute=720)
    _block(client, title="알고리즘", start_minute=660, end_minute=780)

    week = client.get("/calendar/week").json()
    monday = week["days"][0]

    # 10:00~12:00 과 11:00~13:00 은 합쳐서 10:00~13:00 = 180분.
    # 따로 더하면 240분이 된다.
    assert monday["busy_minutes"] == 180


def test_blocks_outside_the_active_window_do_not_count(client):
    """새벽 알바를 빼면 낮에 쓸 시간이 줄어든 것처럼 보인다."""
    _block(client, title="새벽 알바", start_minute=0, end_minute=300)

    monday = client.get("/calendar/week").json()["days"][0]

    assert monday["busy_minutes"] == 0


def test_free_time_is_not_the_same_as_study_time(client):
    """빈 시간을 그대로 쓰지 않는다.

    9시간이 비어도 9시간 공부하지 않는다. 하루 상한과 비교해
    작은 쪽을 제안한다.
    """
    day = client.get("/calendar/day").json()

    assert day["free_minutes"] == 780        # 09:00~22:00
    assert day["daily_cap_minutes"] == 180
    assert day["suggested_minutes"] == 180
    assert day["capped"] is True


def test_suggestion_follows_free_time_when_the_day_is_full(client):
    """상한보다 빈 시간이 적으면 빈 시간이 답이다."""
    client.patch("/calendar/settings", json={"daily_cap_minutes": 600})

    # 09:00~21:00 을 통째로 채운다 → 60분만 남는다
    _block(
        client,
        title="종일 일정",
        weekday=TODAY_WEEKDAY,
        start_minute=540,
        end_minute=1260,
    )

    day = client.get("/calendar/day").json()

    assert day["free_minutes"] == 60
    assert day["suggested_minutes"] == 60
    assert day["capped"] is False


def test_one_off_blocks_do_not_show_up_every_week(client):
    """하루짜리가 주간 격자에 뜨면 매주 반복되는 것처럼 읽힌다."""
    _block(client, weekday=None, date="2026-09-09", title="면접")

    week = client.get("/calendar/week").json()

    assert all(day["blocks"] == [] for day in week["days"])

    # 그날에는 걸린다
    day = client.get("/calendar/day?date=2026-09-09").json()
    assert [b["title"] for b in day["blocks"]] == ["면접"]


def test_active_window_end_must_come_after_start(client):
    bad = client.patch(
        "/calendar/settings",
        json={"day_start_minute": 1200, "day_end_minute": 600},
    )
    assert bad.status_code == 422


def test_blocks_can_be_edited_and_removed(client):
    block = _block(client).json()

    renamed = client.patch(
        f"/calendar/blocks/{block['id']}",
        json={"title": "운영체제", "end_minute": 780},
    ).json()

    assert renamed["title"] == "운영체제"
    assert renamed["end"] == "13:00"
    assert renamed["minutes"] == 180

    client.delete(f"/calendar/blocks/{block['id']}")

    assert client.get("/calendar/blocks").json()["blocks"] == []


# --- 마감 · 종일 ---

def test_a_deadline_belongs_to_a_date_not_a_weekday(client):
    """매주 돌아오는 마감은 없다."""
    weekly = _block(client, kind="deadline", start_minute=None, end_minute=None)
    assert weekly.status_code == 422


def test_a_deadline_does_not_eat_free_time(client):
    """마감은 그날 할 일이 아니라 그날까지의 선이다.

    빈 시간에서 빼면 마감 날 하루가 통째로 사라진다."""
    today = date.today().isoformat()
    before = client.get(f"/calendar/day?date={today}").json()["free_minutes"]

    made = client.post("/calendar/blocks", json={
        "title": "캡스톤 중간 발표", "kind": "deadline", "date": today,
    })
    assert made.status_code == 200
    assert made.json()["all_day"] is True

    after = client.get(f"/calendar/day?date={today}").json()
    assert after["free_minutes"] == before
    assert [b["title"] for b in after["blocks"]] == ["캡스톤 중간 발표"]


def test_an_all_day_block_needs_no_times(client):
    made = client.post("/calendar/blocks", json={
        "title": "학회", "kind": "personal", "date": "2026-10-02", "all_day": True,
    })
    assert made.status_code == 200
    assert made.json()["start"] == "00:00"

    timed = client.post("/calendar/blocks", json={
        "title": "면접", "kind": "personal", "date": "2026-10-02",
    })
    assert timed.status_code == 422


# --- 한 달 ---

def _month_days(client, year=2026, month=9):
    month_view = client.get(f"/calendar/month?year={year}&month={month}").json()
    return month_view, {d["date"]: d for w in month_view["weeks"] for d in w}


def test_the_month_is_whole_weeks_from_monday(client):
    month_view, _ = _month_days(client)
    weeks = month_view["weeks"]

    assert all(len(week) == 7 for week in weeks)
    assert weeks[0][0]["date"] == "2026-08-31"   # 9월 1일은 화요일
    assert weeks[-1][-1]["date"] == "2026-10-04"
    assert [d["in_month"] for d in weeks[0][:2]] == [False, True]


def test_the_month_puts_weekly_one_off_and_posting_deadlines_together(
    client, db_session
):
    """요일 격자로는 "다음 주 목요일에 뭐가 있지?" 를 답할 수 없었다."""
    _block(client, weekday=1, title="추천시스템")              # 화요일
    _block(client, weekday=None, date="2026-09-17", title="면접")

    db_session.add(models.Opportunity(
        title="AI/Data 기획", organization="어떤회사",
        opportunity_type="job", source="manual", status="interested",
        deadline=datetime(2026, 9, 22, 23, 59),
    ))
    db_session.commit()

    _, days = _month_days(client)

    assert [b["title"] for b in days["2026-09-15"]["blocks"]] == ["추천시스템"]
    assert [b["title"] for b in days["2026-09-17"]["blocks"]] == ["면접"]
    assert [d["title"] for d in days["2026-09-22"]["deadlines"]] == ["AI/Data 기획"]


def test_a_withdrawn_application_leaves_the_month(client, db_session):
    """DX 지원을 접었는데 달력에 마감이 남아 있으면 아직 할 일처럼 읽힌다."""
    deadline = datetime(2026, 9, 15, 23, 59)
    posting = models.Opportunity(
        title="인공지능 (AI부문)", organization="한빛전자",
        opportunity_type="job", source="manual", status="interested",
        deadline=deadline,
    )
    db_session.add(posting)
    db_session.flush()
    db_session.add(models.Application(
        opportunity_id=posting.id, status="withdrawn", deadline=deadline,
    ))
    db_session.commit()

    _, days = _month_days(client)

    assert days["2026-09-15"]["deadlines"] == []


def test_calendar_deadlines_reach_the_today_strip_but_not_the_plan(
    client, db_session
):
    """캡스톤 마감을 넣었으면 D-day 띠에 떠야 한다.

    다만 그날까지 무엇을 해야 하는지는 앱이 모른다 — 할 일로 만들지 않는다."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    client.post("/calendar/blocks", json={
        "title": "캡스톤 중간 발표", "kind": "deadline", "date": tomorrow,
    })

    items = client.get("/today/deadlines").json()["deadlines"]
    assert [(i["kind"], i["title"], i["days_left"]) for i in items] == [
        ("event", "캡스톤 중간 발표", 1)
    ]

    candidates = today_service.build_candidates(db_session, date.today())
    assert not any("캡스톤" in c["title"] for c in candidates)
