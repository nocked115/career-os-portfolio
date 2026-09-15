"""루틴과 마감 있는 학습 — 오늘 계획의 순서와 시간.

2026-09-17 은 목요일이다.
"""

from datetime import date, datetime, timedelta

from app import models
from app.services import routine as routine_service
from app.services import today as today_service


THURSDAY = date(2026, 9, 17)


def _routine(db, title, minutes=30, weekdays="0123456", target=None, unit="", path=None):
    routine = models.Routine(
        title=title, minutes=minutes, weekdays=weekdays,
        target_count=target, unit_label=unit, learning_path=path,
        # 루틴을 만들기 전 날은 세지 않는다. 테스트 날짜보다 먼저 만든 것으로 둔다.
        created_at=datetime(2026, 9, 1, 9, 0),
    )
    db.add(routine)
    db.commit()
    return routine


def _path_with_steps(db, title, dues):
    path = models.LearningPath(title=title)
    db.add(path)
    db.flush()
    for position, due in enumerate(dues):
        db.add(models.LearningStep(
            learning_path_id=path.id, title=f"{position + 1}주차", position=position,
            estimated_minutes=45, due_date=due,
        ))
    db.commit()
    db.refresh(path)
    return path


# --------------------------------
# 오늘 계획
# --------------------------------

def test_routines_take_time_first_but_not_the_task_slots(db_session):
    _routine(db_session, "코테", target=3, unit="문제")
    _routine(db_session, "coding rehab")
    in_ten = THURSDAY + timedelta(days=10)
    _path_with_steps(db_session, "Tave", [in_ten, in_ten, in_ten])

    plan = today_service.generate_plan(db_session, 150, "light", today=THURSDAY)

    types = [task["task_type"] for task in plan["tasks"]]
    # 가볍게는 칸이 둘이다. 루틴 둘은 칸을 쓰지 않아서 학습 둘이 그대로 들어간다.
    assert types == ["routine", "routine", "learning_step", "learning_step"]
    assert plan["tasks"][0]["reason"].startswith("매일 하는 일 · 목표 3문제")
    assert sum(task["minutes"] for task in plan["tasks"]) <= 150


def test_an_urgent_learning_deadline_goes_before_routines(db_session):
    _routine(db_session, "코테")
    _path_with_steps(db_session, "Tave", [THURSDAY + timedelta(days=2)])

    plan = today_service.generate_plan(db_session, 120, "normal", today=THURSDAY)

    assert [task["task_type"] for task in plan["tasks"]] == ["learning_step", "routine"]
    assert plan["tasks"][0]["reason"].startswith("마감까지 2일")


def test_an_urgent_learning_deadline_is_not_crowded_out_by_carry_overs(db_session):
    yesterday = THURSDAY - timedelta(days=1)
    for position, title in enumerate(["핸즈온 머신러닝 1장", "AWS Mini Project"]):
        db_session.add(models.DailyPlanTask(
            plan_date=yesterday, position=position, task_type="resource",
            title=title, minutes=45, reason="어제", status="planned",
        ))
    db_session.commit()
    _path_with_steps(db_session, "Tave", [THURSDAY + timedelta(days=3)])

    plan = today_service.generate_plan(db_session, 120, "light", today=THURSDAY)

    # 가볍게는 두 칸. 발표 D-3 이 이월 둘 중 하나보다 앞선다.
    assert [task["title"] for task in plan["tasks"]] == ["Tave — 1주차", "핸즈온 머신러닝 1장"]


def test_a_same_day_deadline_says_today(db_session):
    from app.services import today as service

    assert service._due_text(0) == "오늘 마감입니다"
    assert service._due_text(2) == "마감까지 2일 남았습니다"


def test_a_path_target_date_brings_its_next_step(db_session):
    path = _path_with_steps(db_session, "컴퓨터비전 스프린트", [None, None])
    path.target_date = THURSDAY + timedelta(days=5)
    db_session.commit()

    plan = today_service.generate_plan(db_session, 120, "normal", today=THURSDAY)

    assert plan["tasks"][0]["title"] == "컴퓨터비전 스프린트 — 1주차"


def test_routines_skip_days_that_are_not_theirs(db_session):
    _routine(db_session, "주말 모임 준비", weekdays="56")

    plan = today_service.generate_plan(db_session, 120, "normal", today=THURSDAY)

    assert plan["tasks"] == []


def test_routines_are_not_carried_over(db_session):
    routine = _routine(db_session, "코테")
    db_session.add(models.DailyPlanTask(
        plan_date=THURSDAY - timedelta(days=1), position=0, task_type="routine",
        title="코테", minutes=30, reason="어제", status="planned", routine_id=routine.id,
    ))
    db_session.commit()

    plan = today_service.generate_plan(db_session, 120, "normal", today=THURSDAY)

    assert len(plan["tasks"]) == 1
    assert plan["tasks"][0]["carried_from"] is None


def test_a_finished_routine_is_not_planned_again_the_same_day(db_session):
    _routine(db_session, "코테")

    first = today_service.generate_plan(db_session, 120, "normal", today=THURSDAY)
    task = db_session.get(models.DailyPlanTask, first["tasks"][0]["id"])
    today_service.complete_task(db_session, task)

    again = today_service.generate_plan(db_session, 120, "normal", today=THURSDAY)

    assert [t["status"] for t in again["tasks"]] == ["done"]


# --------------------------------
# 완료 · 기록
# --------------------------------

def test_completing_a_routine_logs_the_count_without_finishing_its_path_step(db_session):
    path = _path_with_steps(db_session, "coding rehab", [None])
    _routine(db_session, "rehab", path=path)
    _routine(db_session, "코테", target=3, unit="문제")

    plan = today_service.generate_plan(db_session, 120, "normal", today=THURSDAY)
    rehab_task, coding_task = [db_session.get(models.DailyPlanTask, t["id"]) for t in plan["tasks"]]

    assert rehab_task.title == "rehab — 1주차"

    result = today_service.complete_task(db_session, coding_task, count=2)
    assert result["effects"] == ["코테 2문제 기록 (목표 3문제)"]

    today_service.complete_task(db_session, rehab_task)
    assert path.steps[0].status == "not_started"
    assert rehab_task.routine.logs[0].log_date == THURSDAY


def test_a_learning_task_with_unchecked_items_keeps_the_step_open(db_session):
    path = _path_with_steps(db_session, "Tave", [THURSDAY + timedelta(days=3)])
    step = path.steps[0]
    db_session.add(models.LearningChecklistItem(
        learning_step_id=step.id, position=0, kind="task", text="논문 정독",
    ))
    db_session.commit()

    plan = today_service.generate_plan(db_session, 120, "normal", today=THURSDAY)
    task = db_session.get(models.DailyPlanTask, plan["tasks"][0]["id"])

    assert "체크 안 한 항목이 1개" in plan["tasks"][0]["on_complete"]

    result = today_service.complete_task(db_session, task)

    assert step.status == "in_progress"
    assert result["effects"] == ["체크 안 한 항목 1개가 남아 단계는 진행 중으로 둡니다"]


# --------------------------------
# 목표 올리기 제안 · API
# --------------------------------

def test_raising_the_target_is_suggested_only_with_a_week_of_evidence(db_session):
    routine = _routine(db_session, "코테", target=3, unit="문제")

    for offset in range(1, 6):
        routine_service.record(db_session, routine, THURSDAY - timedelta(days=offset), 3)
    routine_service.record(db_session, routine, THURSDAY - timedelta(days=6), 1)
    db_session.commit()

    found = routine_service.suggestion(routine, THURSDAY)
    assert found == {"to": 4, "evidence": "지난 7일 중 할 차례였던 7일 가운데 5일 3문제를 채웠어요."}

    routine_service.unrecord(db_session, routine, THURSDAY - timedelta(days=1))
    db_session.commit()
    assert routine_service.suggestion(routine, THURSDAY) is None


def test_days_before_the_routine_existed_are_not_counted_as_missed(db_session):
    from datetime import datetime

    routine = _routine(db_session, "코테", target=3, unit="문제")
    routine.created_at = datetime(2026, 9, 17, 9, 0)   # 목요일에 만들었다
    db_session.commit()

    assert routine_service.week_summary(routine, THURSDAY) == {"due": 0, "done": 0}
    recent = routine_service.recent(routine, THURSDAY)
    assert [day["due"] for day in recent] == [False] * 6 + [True]


def test_routine_api_validates_weekdays_and_logs_a_day(client):
    bad = client.post("/routines", json={"title": "코테", "weekdays": [7]})
    assert bad.status_code == 400

    created = client.post(
        "/routines",
        json={"title": "코테", "minutes": 30, "target_count": 3, "unit_label": "문제"},
    ).json()
    assert created["weekday_label"] == "매일"
    assert created["target_text"] == "3문제"

    today = date.today().isoformat()
    logged = client.put(f"/routines/{created['id']}/logs/{today}", json={"count": 2}).json()
    assert logged["today_log"] == {"count": 2}

    cleared = client.put(f"/routines/{created['id']}/logs/{today}", json={"done": False}).json()
    assert cleared["today_log"] is None

    future = (date.today() + timedelta(days=1)).isoformat()
    assert client.put(f"/routines/{created['id']}/logs/{future}", json={}).status_code == 400


def test_deleting_a_routine_keeps_done_records(client, db_session):
    created = client.post("/routines", json={"title": "코테"}).json()
    db_session.add_all([
        models.DailyPlanTask(plan_date=date.today(), position=0, task_type="routine",
                             title="코테", minutes=30, status="done", routine_id=created["id"]),
        models.DailyPlanTask(plan_date=date.today(), position=1, task_type="routine",
                             title="코테", minutes=30, status="planned", routine_id=created["id"]),
    ])
    db_session.commit()

    body = client.delete(f"/routines/{created['id']}").json()

    assert body["plan"] == {"removed": 1, "kept": 1}


def test_a_step_due_date_can_be_set(client):
    path = client.post("/learning-paths", json={"title": "Tave"}).json()
    step = client.post(
        "/learning-steps", json={"learning_path_id": path["id"], "title": "CLIP", "position": 0}
    ).json()

    updated = client.patch(f"/learning-steps/{step['id']}", json={"due_date": "2026-09-20"}).json()

    assert updated["due_date"] == "2026-09-20"
