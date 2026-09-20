"""루틴을 어떻게 시작하는가 — 오늘 카드가 갈 곳을 알아야 한다."""

from datetime import date

from app import models
from app.services import today as today_service


def test_the_link_and_note_reach_the_today_card(client, db_session):
    created = client.post("/routines", json={
        "title": "코테", "minutes": 30, "target_count": 3, "unit_label": "문제",
        "link_url": "https://school.programmers.co.kr/learn/challenges",
        "note": "Lv.1에서 안 푼 문제 위에서부터",
    }).json()

    assert created["link_url"] == "https://school.programmers.co.kr/learn/challenges"

    task = models.DailyPlanTask(
        plan_date=date.today(), position=0, task_type="routine", title="코테",
        minutes=30, reason="매일", status="planned", routine_id=created["id"],
    )
    db_session.add(task)
    db_session.commit()

    summary = today_service.serialize_task(task)["routine"]

    assert summary["link_url"] == "https://school.programmers.co.kr/learn/challenges"
    assert summary["note"] == "Lv.1에서 안 푼 문제 위에서부터"
    assert summary["target_count"] == 3


def test_a_routine_without_a_link_is_fine(client):
    created = client.post("/routines", json={"title": "coding rehab"}).json()

    assert created["link_url"] == ""
    assert created["note"] == ""


def test_unsafe_links_are_refused(client):
    created = client.post("/routines", json={"title": "코테"}).json()

    assert client.post("/routines", json={
        "title": "나쁜 루틴", "link_url": "javascript:alert(1)",
    }).status_code == 422
    assert client.patch(f"/routines/{created['id']}", json={
        "link_url": "javascript:alert(1)",
    }).status_code == 422
