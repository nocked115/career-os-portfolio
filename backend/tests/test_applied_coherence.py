"""지원하면 세 화면이 같이 움직여야 한다.

수현: "지원 완료 했는데 지금 기회에도 그대로 남아있고 오늘 계획에도 있고
난리다 난리야."

SK인텔릭스에 지원한 당일 오후에도 오늘 계획에 "지원할지 정하기 — ...
아직 지원서를 만들지 않았습니다" 가 그대로 떠 있었다.
"""

from datetime import date, datetime, timedelta

from app import models
from app.services import today as today_service


TODAY = date.today()


def _posting(db, title="데이터 분석 인턴", days=3):
    row = models.Opportunity(
        opportunity_type="job", title=title, organization="SK인텔릭스",
        source="manual", status="interested",
        deadline=datetime.combine(TODAY + timedelta(days=days), datetime.min.time()),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_an_application_without_a_deadline_still_covers_the_posting(db_session):
    """마감일은 후보를 고를 때 필요한 것이지 '이미 정했는가' 와 무관하다.

    전에는 `deadline IS NOT NULL` 인 지원서만 봐서, 마감일을 안 적은
    지원서의 공고가 매일 "아직 지원서를 만들지 않았습니다" 로 되살아났다.
    """
    posting = _posting(db_session)

    db_session.add(models.Application(
        opportunity_id=posting.id, status="applied",
        applied_at=datetime.now(), deadline=None,       # ← 마감일 없음
    ))
    db_session.commit()

    titles = [
        item["title"] for item in today_service.build_candidates(db_session, TODAY)
    ]

    assert not any("지원할지 정하기" in title for title in titles)


def test_a_posting_without_an_application_still_asks(db_session):
    _posting(db_session)

    titles = [
        item["title"] for item in today_service.build_candidates(db_session, TODAY)
    ]

    assert any("지원할지 정하기" in title for title in titles)


def test_creating_an_application_finishes_todays_task(client, db_session):
    """다시 짤 때까지 기다리면 이미 지원한 공고가 오늘 할 일로 남아 있다."""
    posting = _posting(db_session)

    task = models.DailyPlanTask(
        plan_date=TODAY, position=0, task_type="opportunity",
        title=f"지원할지 정하기 — {posting.title}", minutes=15,
        reason="오늘 마감입니다.", status="planned", opportunity_id=posting.id,
    )
    db_session.add(task)
    db_session.commit()

    client.post("/applications", json={
        "opportunity_id": posting.id, "status": "applied",
    })

    db_session.expire_all()
    # 넘긴 것이 아니라 끝낸 것이다 — 정하는 일은 실제로 끝났다.
    assert task.status == "done"
    assert task.completed_at is not None


def test_other_postings_are_left_alone(client, db_session):
    mine = _posting(db_session, "내가 지원한 것")
    other = _posting(db_session, "다른 공고")

    other_task = models.DailyPlanTask(
        plan_date=TODAY, position=0, task_type="opportunity",
        title="지원할지 정하기 — 다른 공고", minutes=15, reason="",
        status="planned", opportunity_id=other.id,
    )
    db_session.add(other_task)
    db_session.commit()

    client.post("/applications", json={"opportunity_id": mine.id, "status": "applied"})

    db_session.expire_all()
    assert other_task.status == "planned"


def test_a_parked_task_is_settled_too(client, db_session):
    """빼둔 것도 끝난 것이다 — 거기 남아 있으면 매일 보인다."""
    posting = _posting(db_session)

    task = models.DailyPlanTask(
        plan_date=TODAY - timedelta(days=5), position=0, task_type="opportunity",
        title="지원할지 정하기 — 데이터 분석 인턴", minutes=15, reason="",
        status=today_service.PARKED, opportunity_id=posting.id,
    )
    db_session.add(task)
    db_session.commit()

    client.post("/applications", json={"opportunity_id": posting.id, "status": "applied"})

    db_session.expire_all()
    assert task.status == "done"


def test_applying_clears_the_favorite(client, db_session):
    """즐겨찾기는 "잊지 않게 여기 둬" 다. 지원서를 낸 뒤에는 잊을 일이 없다."""
    posting = _posting(db_session)
    posting.favorite = True
    db_session.commit()

    client.post("/applications", json={
        "opportunity_id": posting.id, "status": "applied",
    })

    db_session.expire_all()
    assert posting.favorite is False


def test_another_postings_favorite_is_kept(client, db_session):
    mine = _posting(db_session, "내가 지원한 것")
    other = _posting(db_session, "다른 공고")
    other.favorite = True
    db_session.commit()

    client.post("/applications", json={"opportunity_id": mine.id, "status": "applied"})

    db_session.expire_all()
    assert other.favorite is True
