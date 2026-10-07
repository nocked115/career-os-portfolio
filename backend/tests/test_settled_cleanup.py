"""답이 이미 정해진 이월은 묻지 않는다.

수현: "지울 거는 지워야 하는데 알아서 안 지워서."

"이건 안 할 건가요?" 칸이 열한 줄이 됐는데, 그중 여럿은 답이 이미
정해진 것이었다 — 마감이 지난 공고, 이미 지원서를 만든 공고. 사실을
질문으로 내밀면 진짜 물어볼 것들이 거기 묻힌다.
"""

from datetime import date, timedelta

from app import models
from app.services import today as today_service


TODAY = date(2026, 10, 6)
OLD = TODAY - timedelta(days=10)


def _task(db, title, task_type="opportunity", **fields):
    task = models.DailyPlanTask(
        plan_date=OLD, position=0, task_type=task_type,
        title=title, minutes=20, reason="어제", status="planned",
        **fields,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _opportunity(db, deadline=None, status="interested"):
    row = models.Opportunity(
        opportunity_type="job", title="공고", source="test",
        deadline=deadline, status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _stale_titles(db):
    return [row["title"] for row in today_service.stale_carry_overs(db, TODAY)]


def test_a_posting_past_its_deadline_is_not_asked_about(db_session):
    """지원할 수 없는 것에 '지원할지 정하기' 를 물을 수는 없다."""
    closed = _opportunity(db_session, deadline=TODAY - timedelta(days=1))
    _task(db_session, "지원할지 정하기 — 마감됨", opportunity_id=closed.id)

    assert _stale_titles(db_session) == []


def test_an_open_posting_is_still_asked_about(db_session):
    live = _opportunity(db_session, deadline=TODAY + timedelta(days=5))
    _task(db_session, "지원할지 정하기 — 열려 있음", opportunity_id=live.id)

    assert _stale_titles(db_session) == ["지원할지 정하기 — 열려 있음"]


def test_a_posting_i_already_applied_to_is_settled(db_session):
    """정하기는 끝났다."""
    row = _opportunity(db_session, deadline=TODAY + timedelta(days=30))
    db_session.add(models.Application(opportunity_id=row.id, status="submitted"))
    db_session.commit()

    _task(db_session, "지원할지 정하기 — 이미 냄", opportunity_id=row.id)

    assert _stale_titles(db_session) == []


def test_a_posting_i_dropped_is_settled(db_session):
    row = _opportunity(
        db_session, deadline=TODAY + timedelta(days=30), status="not_interested"
    )
    _task(db_session, "지원할지 정하기 — 안 감", opportunity_id=row.id)

    assert _stale_titles(db_session) == []


def test_a_finished_step_is_settled(db_session):
    path = models.LearningPath(title="경로")
    db_session.add(path)
    db_session.flush()
    step = models.LearningStep(
        learning_path_id=path.id, title="1주차", position=0,
        estimated_minutes=60, status="completed",
    )
    db_session.add(step)
    db_session.commit()

    _task(db_session, "경로 — 1주차", task_type="learning_step", learning_step_id=step.id)

    assert _stale_titles(db_session) == []


def test_clearing_marks_them_skipped_not_deleted(db_session):
    """자국이 남아야 되돌릴 수 있다. 조용히 없애지 않는다."""
    closed = _opportunity(db_session, deadline=TODAY - timedelta(days=1))
    task = _task(db_session, "지원할지 정하기 — 마감됨", opportunity_id=closed.id)

    cleared = today_service.clear_settled_tasks(db_session, TODAY)

    assert [row["reason"] for row in cleared] == [today_service.SETTLED_DEADLINE]
    db_session.refresh(task)
    assert task.status == "skipped"
    assert db_session.get(models.DailyPlanTask, task.id) is not None


def test_a_settled_task_does_not_carry_over_into_the_plan(db_session):
    """다시 짜도 안 올라온다. 안 그러면 내일 또 같은 줄이 생긴다."""
    closed = _opportunity(db_session, deadline=TODAY - timedelta(days=1))
    _task(db_session, "지원할지 정하기 — 마감됨", opportunity_id=closed.id)

    titles = [
        item["title"] for item in today_service._carry_over_candidates(db_session, TODAY)
    ]

    assert "지원할지 정하기 — 마감됨" not in titles
