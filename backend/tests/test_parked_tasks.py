"""기한 없이 빼두는 자리 — "언젠가 할 일".

치우기(skip)는 그날로 끝나지만 이건 남는다. 날짜에 묶이지 않아서
다음 날에도 보이고, 거기서 바로 완료할 수 있다.
"""

from datetime import date, timedelta

from app import models


def _add_free_line(client, title="논문 초록 다시 읽기", minutes=20):
    body = client.post("/today/tasks", json={
        "kind": "custom", "title": title, "minutes": minutes,
    }).json()

    return next(t for t in body["plan"]["tasks"] if t["title"] == title)


def test_a_parked_line_leaves_today_and_waits(client):
    task = _add_free_line(client)

    client.post(f"/today/tasks/{task['id']}/park")
    plan = client.get("/today/plan").json()

    assert [t["title"] for t in plan["tasks"]] == []
    assert [t["title"] for t in plan["parked"]] == ["논문 초록 다시 읽기"]


def test_parked_minutes_do_not_eat_today(client):
    task = _add_free_line(client, minutes=45)
    before = client.get("/today/plan").json()["planned_minutes"]

    client.post(f"/today/tasks/{task['id']}/park")
    after = client.get("/today/plan").json()

    assert before == 45
    assert after["planned_minutes"] == 0
    assert after["remaining_minutes"] == after["available_minutes"]


def test_a_parked_line_is_not_carried_over(client, db_session):
    task = _add_free_line(client)
    client.post(f"/today/tasks/{task['id']}/park")

    # 어제 빼둔 것처럼 날짜를 밀어 둔다.
    row = db_session.get(models.DailyPlanTask, task["id"])
    row.plan_date = date.today() - timedelta(days=1)
    db_session.commit()

    plan = client.post("/today/plan").json()

    assert [t["title"] for t in plan["tasks"]] == []
    assert [t["title"] for t in plan["parked"]] == ["논문 초록 다시 읽기"]


def test_a_parked_line_survives_replanning(client):
    task = _add_free_line(client)
    client.post(f"/today/tasks/{task['id']}/park")

    plan = client.post("/today/plan").json()

    assert [t["title"] for t in plan["parked"]] == ["논문 초록 다시 읽기"]


def test_a_parked_line_can_be_finished_where_it_sits(client):
    task = _add_free_line(client)
    client.post(f"/today/tasks/{task['id']}/park")

    assert client.post(f"/today/tasks/{task['id']}/complete").status_code == 200

    plan = client.get("/today/plan").json()
    assert plan["parked"] == []
    assert [t["status"] for t in plan["tasks"]] == ["done"]


def test_a_parked_line_comes_back_to_today(client):
    task = _add_free_line(client)
    client.post(f"/today/tasks/{task['id']}/park")

    client.post(f"/today/tasks/{task['id']}/unpark")
    plan = client.get("/today/plan").json()

    assert plan["parked"] == []
    assert [t["title"] for t in plan["tasks"]] == ["논문 초록 다시 읽기"]


def test_finished_work_cannot_be_parked(client):
    task = _add_free_line(client)
    client.post(f"/today/tasks/{task['id']}/complete")

    assert client.post(f"/today/tasks/{task['id']}/park").status_code == 409


def test_only_parked_lines_can_be_unparked(client):
    task = _add_free_line(client)

    assert client.post(f"/today/tasks/{task['id']}/unpark").status_code == 409
