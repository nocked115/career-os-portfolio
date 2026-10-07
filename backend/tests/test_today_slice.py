"""오늘은 이 주차에서 어디서부터 어디까지.

수현: "각 주차에서 무엇을 해야 한다 → 그 안에서 세부적으로 잘라서
오늘은 여기서부터 여기까지 이게 나와야 할 것 같은데."

주차 하나가 9시간이면 그걸 통째로 "오늘 할 일" 이라고 내밀 수 없다.
"""

from app import models
from app.services import checklist


def _step(db, minutes, items, done=0):
    path = models.LearningPath(title="경로")
    db.add(path)
    db.flush()

    step = models.LearningStep(
        learning_path_id=path.id, title="1주차", position=0,
        estimated_minutes=minutes,
    )
    db.add(step)
    db.flush()

    for position in range(items):
        db.add(models.LearningChecklistItem(
            learning_step_id=step.id, position=position,
            text=f"항목 {position + 1}", done=position < done,
        ))

    db.commit()
    db.refresh(step)
    return step


def test_a_nine_hour_week_is_cut_to_todays_share(db_session):
    """9시간 주차, 항목 12개 → 한 항목 45분. 오늘 90분이면 2개."""
    step = _step(db_session, minutes=540, items=12)

    today = checklist.today_slice(step, minutes=90)

    assert today["count"] == 2
    assert today["from_number"] == 1
    assert today["to_number"] == 2
    assert today["total_number"] == 12
    assert today["minutes"] == 90
    assert today["finishes_step"] is False


def test_it_starts_after_what_is_already_done(db_session):
    """사람이 세는 번호로 말한다 — position 은 0부터라 화면 숫자와 어긋난다."""
    step = _step(db_session, minutes=540, items=12, done=5)

    today = checklist.today_slice(step, minutes=90)

    assert today["from_number"] == 6
    assert today["to_number"] == 7
    assert today["items"] == ["항목 6", "항목 7"]


def test_the_last_slice_says_it_finishes_the_week(db_session):
    step = _step(db_session, minutes=540, items=12, done=11)

    today = checklist.today_slice(step, minutes=180)

    assert today["count"] == 1
    assert today["finishes_step"] is True


def test_at_least_one_item_is_given(db_session):
    """0개를 '오늘 할 일' 이라고 내밀 수 없다."""
    step = _step(db_session, minutes=600, items=2)   # 한 항목 300분

    assert checklist.today_slice(step, minutes=30)["count"] == 1


def test_without_times_nothing_is_cut(db_session):
    """단계에 시간이 없으면 나눌 기준이 없다. 지어내지 않는다."""
    step = _step(db_session, minutes=0, items=5)

    today = checklist.today_slice(step, minutes=60)

    assert today["count"] == 5
    assert today["minutes"] is None


def test_a_finished_week_has_no_slice(db_session):
    step = _step(db_session, minutes=540, items=3, done=3)

    assert checklist.today_slice(step, minutes=90) is None


def test_a_step_without_a_checklist_has_no_slice(db_session):
    step = _step(db_session, minutes=540, items=0)

    assert checklist.today_slice(step, minutes=90) is None
