"""읽고 남긴 한 줄.

수현: "어디부터 어디 읽고 **정리하기** 이런 식으로 나와야 하는데."

읽기만 하고 아무것도 안 남으면 나중에 "이 책에서 뭘 얻었나" 에 답할 수
없고, 경험 · 포트폴리오로 옮길 재료도 없다.
"""

from app import models
from app.services import today as today_service


def _book(db, label_count=2):
    skill = models.Skill(name="Machine Learning", category="ai", level=1)
    db.add(skill)
    db.flush()

    resource = models.LearningResource(
        title="핸즈온 머신러닝", resource_type="book", url="",
        skill_id=skill.id,
    )
    db.add(resource)
    db.flush()

    for position in range(label_count):
        db.add(models.LearningResourceSegment(
            learning_resource_id=resource.id,
            position=position,
            label=f"{position + 1}장",
            estimated_minutes=45,
            status="not_started",
        ))

    db.commit()
    db.refresh(resource)
    return resource


def test_a_note_is_saved_when_finishing(client, db_session):
    book = _book(db_session)
    first = sorted(book.segments, key=lambda s: s.position)[0]

    client.post(
        f"/segments/{first.id}/complete",
        json={"note": "비용함수가 왜 볼록이어야 하는지 아직 안 잡힌다"},
    )

    db_session.expire_all()
    assert first.status == "completed"
    assert "볼록" in first.note


def test_finishing_without_a_note_still_works(client, db_session):
    """정리는 적어도 되고 안 적어도 된다. 안 적었다고 못 끝내면 안 된다."""
    book = _book(db_session)
    first = sorted(book.segments, key=lambda s: s.position)[0]

    assert client.post(f"/segments/{first.id}/complete").status_code == 200

    db_session.expire_all()
    assert first.status == "completed"
    assert first.note == ""


def test_an_absent_note_does_not_erase_what_was_written(db_session):
    """None 과 빈 문자열은 다르다 — 안 보낸 것과 지우는 것."""
    from app.services import library as library_service

    book = _book(db_session)
    first = sorted(book.segments, key=lambda s: s.position)[0]
    first.note = "적어 둔 것"
    db_session.commit()

    library_service.complete_segment(db_session, first, note=None)
    assert first.note == "적어 둔 것"

    library_service.complete_segment(db_session, first, note="")
    assert first.note == ""


def test_the_plan_task_carries_the_last_note(db_session):
    """이어 읽을 때 "지난번에 뭐였더라" 가 화면에 있어야 다시 안 열어본다."""
    from datetime import date

    book = _book(db_session, label_count=3)
    segments = sorted(book.segments, key=lambda s: s.position)

    segments[0].status = "completed"
    segments[0].note = "1장은 전체 지도였다"
    db_session.commit()

    task = models.DailyPlanTask(
        plan_date=date.today(), position=0, task_type="resource",
        title="핸즈온 머신러닝 — 2장", minutes=45, reason="직접 넣었습니다.",
        status="planned", learning_resource_id=book.id,
    )
    db_session.add(task)
    db_session.commit()

    payload = today_service.serialize_task(task)["resource"]

    assert payload["next_segment"]["label"] == "2장"
    assert payload["last_note"]["note"] == "1장은 전체 지도였다"
    assert payload["last_note"]["label"] == "1장"


def test_there_is_no_last_note_before_anything_is_written(db_session):
    from datetime import date

    book = _book(db_session)
    task = models.DailyPlanTask(
        plan_date=date.today(), position=0, task_type="resource",
        title="핸즈온 머신러닝", minutes=45, reason="직접 넣었습니다.",
        status="planned", learning_resource_id=book.id,
    )
    db_session.add(task)
    db_session.commit()

    assert today_service.serialize_task(task)["resource"]["last_note"] is None
