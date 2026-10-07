"""실제로 걸린 시간과 못 한 까닭.

수현: "실제 걸리는 시간을 적는 칸을 줄 수 있을까? 아니면 못 한 이유라도.
시간을 넣으면 그 학습 시간에 맞춰서 해줄 수 있잖아."

앱은 "180분" 이라고 적어 두고 실제로 얼마나 걸렸는지 한 번도 묻지 않았다.
오늘 몫을 자르는 것도, 구간 속도도 전부 그 검증 안 된 추정 위에 있었다.
"""

from datetime import date, timedelta

from app import models
from app.services import checklist, today as today_service


TODAY = date.today()


def _task(db, planned, actual=None, status="planned", day_offset=0):
    task = models.DailyPlanTask(
        plan_date=TODAY - timedelta(days=day_offset), position=0,
        task_type="learning_step", title="공부", minutes=planned,
        reason="", status=status, actual_minutes=actual,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_actual_minutes_are_saved_on_completion(client, db_session):
    task = _task(db_session, planned=30)

    client.post(f"/today/tasks/{task.id}/complete", json={"actual_minutes": 55})

    db_session.expire_all()
    assert task.actual_minutes == 55
    assert task.status == "done"


def test_finishing_without_the_time_still_works(client, db_session):
    """적어야만 끝낼 수 있게 하면 적기 싫어서 안 끝내게 된다."""
    task = _task(db_session, planned=30)

    assert client.post(f"/today/tasks/{task.id}/complete").status_code == 200

    db_session.expire_all()
    assert task.status == "done"
    assert task.actual_minutes is None


def test_the_gap_is_reported(client, db_session):
    task = _task(db_session, planned=30)

    body = client.post(
        f"/today/tasks/{task.id}/complete", json={"actual_minutes": 55}
    ).json()

    assert any("계획 30분 → 실제 55분 (+25분)" in e for e in body["effects"])


def test_a_small_gap_is_not_reported(client, db_session):
    """5분 차이를 매번 말하면 읽지 않게 된다."""
    task = _task(db_session, planned=30)

    body = client.post(
        f"/today/tasks/{task.id}/complete", json={"actual_minutes": 33}
    ).json()

    assert not any("실제" in e for e in body["effects"])


def test_a_skip_reason_is_saved(client, db_session):
    """안 한 것도 기록이다 — 같은 까닭이 반복되면 계획이 틀린 것이다."""
    task = _task(db_session, planned=30)

    client.post(f"/today/tasks/{task.id}/skip", json={"reason": "캡스톤 발표 준비"})

    db_session.expire_all()
    assert task.status == "skipped"
    assert task.skip_reason == "캡스톤 발표 준비"


# --------------------------------
# 보정
# --------------------------------

def test_too_few_records_give_no_factor(db_session):
    """두세 번으로 "1.4배 걸린다" 고 말할 수 없다."""
    for i in range(3):
        _task(db_session, planned=30, actual=45, status="done", day_offset=i)

    assert today_service.pace_factor(db_session) is None


def test_the_factor_is_the_ratio_of_actual_to_planned(db_session):
    for i in range(5):
        _task(db_session, planned=30, actual=42, status="done", day_offset=i)

    found = today_service.pace_factor(db_session)

    assert found["samples"] == 5
    assert found["factor"] == 1.4


def test_one_wild_record_does_not_run_away_with_it(db_session):
    """한 번 크게 어긋난 기록이 전체를 끌고 가지 않게 한다."""
    for i in range(5):
        _task(db_session, planned=30, actual=30, status="done", day_offset=i)
    _task(db_session, planned=10, actual=600, status="done", day_offset=9)

    assert today_service.pace_factor(db_session)["factor"] <= today_service.PACE_CEIL


def test_the_slice_shrinks_when_things_take_longer(db_session):
    """계획보다 1.4배 걸렸다면 30분에 다섯 항목이 아니라 세 항목이 맞다."""
    path = models.LearningPath(title="경로")
    db_session.add(path)
    db_session.flush()
    step = models.LearningStep(
        learning_path_id=path.id, title="1주차", position=0, estimated_minutes=160,
    )
    db_session.add(step)
    db_session.flush()
    for position in range(16):
        db_session.add(models.LearningChecklistItem(
            learning_step_id=step.id, position=position, text=f"항목 {position + 1}",
        ))
    db_session.commit()
    db_session.refresh(step)

    # 한 항목 10분. 보정 없이 30분이면 3개.
    plain = checklist.today_slice(step, minutes=30)
    assert plain["count"] == 3
    assert plain["adjusted"] is False

    # 1.5배 걸린다면 한 항목이 15분이므로 2개.
    slower = checklist.today_slice(step, minutes=30, factor=1.5)
    assert slower["count"] == 2
    assert slower["adjusted"] is True
