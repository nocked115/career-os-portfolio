"""알리미 — 날짜가 있는 것을 한 판에.

수현: "오늘 할 일에 들어가는 거 말고 게시판처럼. 오늘 마감 ·
역량검사 대비 (10/18 일) 이런 것도 알리미처럼."

일을 시키는 판이 아니라 알려 주는 판이다. 시간을 재지 않고, 진행률을
움직이지 않고, 오늘 쓸 수 있는 시간에서 빠지지 않는다.
"""

from datetime import date, datetime, timedelta

from app import models
from app.services import reminder


TODAY = date.today()


def test_nothing_to_tell_is_an_empty_board(db_session):
    assert reminder.gather(db_session)["count"] == 0


def test_what_i_write_down_shows_up(client):
    created = client.post("/reminders", json={
        "title": "친구에게 논문 전달",
        "due": TODAY.isoformat(),
    })

    assert created.status_code == 201

    board = client.get("/reminders").json()
    assert board["days"][0]["days_away"] == 0
    assert board["days"][0]["items"][0]["title"].startswith("친구에게")
    assert board["days"][0]["items"][0]["source"] == "mine"


def test_a_posting_deadline_comes_up_on_its_own(client, db_session):
    """알릴 것의 대부분은 앱이 이미 안다. 흩어져 있었을 뿐이다."""
    db_session.add(models.Opportunity(
        opportunity_type="job", title="Data Scientist", organization="에스케이이노베이션",
        source="manual", status="interested",
        deadline=datetime.combine(TODAY + timedelta(days=1), datetime.min.time()),
    ))
    db_session.commit()

    board = client.get("/reminders").json()
    item = board["days"][0]["items"][0]

    assert item["label"] == "공고 마감"
    assert item["where"] == "에스케이이노베이션"
    assert item["source"] == "app"


def test_an_exam_is_on_the_board(client, db_session):
    db_session.add(models.CalendarBlock(
        title="추천시스템 중간고사", kind="exam",
        date=TODAY + timedelta(days=3), start_minute=600, end_minute=720,
    ))
    db_session.commit()

    item = client.get("/reminders").json()["days"][0]["items"][0]

    assert item["label"] == "시험"
    assert item["at"] == "10:00"


def test_a_learning_due_date_is_on_the_board(client, db_session):
    """수현이 든 예시가 바로 이것 — "역량검사 대비 (10/18 일)"."""
    path = models.LearningPath(title="코테")
    db_session.add(path)
    db_session.flush()
    db_session.add(models.LearningStep(
        learning_path_id=path.id, title="역량검사 대비",
        position=0, due_date=TODAY + timedelta(days=1),
    ))
    db_session.commit()

    item = client.get("/reminders").json()["days"][0]["items"][0]

    assert item["label"] == "학습 마감"
    assert item["where"] == "코테"


def test_a_finished_step_stops_telling_me(client, db_session):
    path = models.LearningPath(title="코테")
    db_session.add(path)
    db_session.flush()
    db_session.add(models.LearningStep(
        learning_path_id=path.id, title="끝낸 것", position=0,
        due_date=TODAY + timedelta(days=1), status="completed",
    ))
    db_session.commit()

    assert client.get("/reminders").json()["count"] == 0


def test_far_away_things_are_not_alerts(client, db_session):
    """더 멀면 알림이 아니라 달력이다."""
    db_session.add(models.CalendarBlock(
        title="기말고사", kind="exam", date=TODAY + timedelta(days=40),
        start_minute=600, end_minute=720,
    ))
    db_session.commit()

    assert client.get("/reminders").json()["count"] == 0


def test_marking_it_done_takes_it_off_the_board(client):
    created = client.post("/reminders", json={
        "title": "Tave 강남", "due": TODAY.isoformat(), "at": "10:00",
    }).json()

    client.post(f"/reminders/{created['id']}/done")

    assert client.get("/reminders").json()["count"] == 0


def test_the_board_does_not_touch_todays_budget(client, db_session):
    """할 일이 아니라 알림이다. 오늘 쓸 수 있는 시간이 줄면 안 된다."""
    before = client.get("/today/plan").json()["planned_minutes"]

    client.post("/reminders", json={
        "title": "ScareBlock PPT", "due": TODAY.isoformat(),
    })

    assert client.get("/today/plan").json()["planned_minutes"] == before
