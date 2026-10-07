"""단계가 덮는 자료의 장.

수현: "내가 가진 자료 이거 어떻게 연동시켜, 내가 학습 완료 누르면
그 해당 챕터가 완료되었다고 그것도 판정되려고 하는데."

연결이 자료 단위(단계 ↔ 책)뿐이라 "3주차는 핸즈온 4장" 을 적을 자리가
없었다. 그래서 단계를 끝내도 그 장이 그대로 남아, 같은 공부를 두 군데서
체크해야 했다.
"""

from app import models
from app.services import learning as learning_service


def _setup(db, chapters=3):
    skill = models.Skill(name="Machine Learning", category="ai", level=0)
    db.add(skill)
    db.flush()

    path = models.LearningPath(title="경로", skill_id=skill.id)
    db.add(path)
    db.flush()

    step = models.LearningStep(
        learning_path_id=path.id, title="3주차", position=0,
        estimated_minutes=90, status="in_progress",
    )
    db.add(step)

    resource = models.LearningResource(
        title="핸즈온 머신러닝", resource_type="book", url="", skill_id=skill.id,
    )
    db.add(resource)
    db.flush()

    for position in range(chapters):
        db.add(models.LearningResourceSegment(
            learning_resource_id=resource.id, position=position,
            label=f"{position + 1}장", estimated_minutes=45, status="not_started",
        ))

    db.commit()
    db.refresh(step)
    db.refresh(resource)
    return step, resource


def _segments(resource):
    return sorted(resource.segments, key=lambda s: s.position)


def test_attaching_a_chapter_also_links_the_book(client, db_session):
    """장을 덮는데 책이 안 걸려 있으면 세션 화면에서 그 자료가 안 보인다."""
    step, resource = _setup(db_session)
    chapter = _segments(resource)[0]

    body = client.post(
        f"/learning-steps/{step.id}/segments/{chapter.id}"
    ).json()

    assert body["label"] == "1장"
    db_session.expire_all()
    assert chapter.learning_step_id == step.id
    assert resource in step.resources


def test_finishing_the_step_finishes_its_chapters(client, db_session):
    step, resource = _setup(db_session)
    chapters = _segments(resource)

    for chapter in chapters[:2]:
        client.post(f"/learning-steps/{step.id}/segments/{chapter.id}")

    body = client.post(f"/learning-steps/{step.id}/complete").json()

    db_session.expire_all()
    assert [c.status for c in _segments(resource)] == [
        "completed", "completed", "not_started"
    ]
    assert any("1장" in effect for effect in body["effects"])
    assert any("2장" in effect for effect in body["effects"])


def test_a_chapter_not_attached_is_left_alone(client, db_session):
    """붙이지 않은 장까지 끝내면 안 읽은 걸 읽었다고 하는 것이다."""
    step, resource = _setup(db_session)

    client.post(f"/learning-steps/{step.id}/complete")

    db_session.expire_all()
    assert all(c.status == "not_started" for c in _segments(resource))


def test_finishing_every_chapter_finishes_the_book(client, db_session):
    step, resource = _setup(db_session, chapters=2)

    for chapter in _segments(resource):
        client.post(f"/learning-steps/{step.id}/segments/{chapter.id}")

    client.post(f"/learning-steps/{step.id}/complete")

    db_session.expire_all()
    assert resource.status == "completed"


def test_a_chapter_belongs_to_one_step_only(client, db_session):
    """4장을 3주차와 5주차가 같이 덮는 일은 없다. 붙이면 옮겨진다."""
    step, resource = _setup(db_session)
    other = models.LearningStep(
        learning_path_id=step.learning_path_id, title="4주차",
        position=1, estimated_minutes=90,
    )
    db_session.add(other)
    db_session.commit()

    chapter = _segments(resource)[0]

    client.post(f"/learning-steps/{step.id}/segments/{chapter.id}")
    client.post(f"/learning-steps/{other.id}/segments/{chapter.id}")

    db_session.expire_all()
    assert chapter.learning_step_id == other.id


def test_detaching(client, db_session):
    step, resource = _setup(db_session)
    chapter = _segments(resource)[0]

    client.post(f"/learning-steps/{step.id}/segments/{chapter.id}")
    client.delete(f"/learning-steps/{step.id}/segments/{chapter.id}")

    db_session.expire_all()
    assert chapter.learning_step_id is None


def test_a_chapter_can_be_picked_without_linking_the_book_first(db_session):
    """두 단계로 나뉘면 번거롭다 — 장을 붙이면 그 책도 같이 걸린다.

    후보는 **이 경로의 스킬** 로 등록된 자료에서 온다. 라이브러리 전체를
    내밀면 고를 수가 없다.
    """
    step, resource = _setup(db_session)

    # 자료를 단계에 **연결하지 않은** 상태
    assert resource not in step.resources

    payload = learning_service._step_segments(db_session, step)

    assert [s["label"] for s in payload["available"]] == ["1장", "2장", "3장"]


def test_a_book_for_another_skill_is_not_offered(db_session):
    other = models.Skill(name="SQL", category="data", level=0)
    db_session.add(other)
    db_session.flush()

    step, _ = _setup(db_session)

    unrelated = models.LearningResource(
        title="SQL 책", resource_type="book", url="", skill_id=other.id,
    )
    db_session.add(unrelated)
    db_session.flush()
    db_session.add(models.LearningResourceSegment(
        learning_resource_id=unrelated.id, position=0,
        label="SQL 1장", estimated_minutes=30, status="not_started",
    ))
    db_session.commit()

    labels = [
        s["label"]
        for s in learning_service._step_segments(db_session, step)["available"]
    ]

    assert "SQL 1장" not in labels


def test_the_session_shows_attached_and_choosable_chapters(db_session):
    """붙은 것은 후보에서 빠진다."""
    step, resource = _setup(db_session)
    chapters = _segments(resource)

    chapters[0].learning_step_id = step.id
    step.resources.append(resource)
    db_session.commit()

    payload = learning_service._step_segments(db_session, step)

    assert [s["label"] for s in payload["attached"]] == ["1장"]
    assert [s["label"] for s in payload["available"]] == ["2장", "3장"]
    assert payload["attached"][0]["resource_title"] == "핸즈온 머신러닝"
