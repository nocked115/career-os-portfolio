"""다른 세션에 넘길 프롬프트 — 저장된 것만, 없는 것은 없다고."""

from datetime import date

from app import models


def _setup(db, description="매주 논문 읽고 발표. 코드는 GitHub, 메모는 Notion."):
    path = models.LearningPath(title="Tave 논문 스터디", description=description)
    db.add(path)
    db.flush()
    first = models.LearningStep(learning_path_id=path.id, title="1주차 — CLIP", position=0,
                                status="completed")
    second = models.LearningStep(learning_path_id=path.id, title="2주차 — SAM", position=1,
                                 due_date=date(2026, 9, 26), estimated_minutes=60)
    db.add_all([first, second])
    db.flush()
    db.add_all([
        models.LearningChecklistItem(learning_step_id=second.id, position=0, section="정독",
                                     kind="task", text="논문 정독", done=True),
        models.LearningChecklistItem(learning_step_id=second.id, position=1, section="실습",
                                     kind="task", text="`SamPredictor` 데모 실행"),
        models.LearningChecklistItem(learning_step_id=second.id, position=2, kind="link",
                                     text="SAM 저장소", url="https://github.com/facebookresearch/segment-anything"),
    ])
    db.commit()
    return second


def test_the_handoff_carries_track_step_progress_and_format(client, db_session):
    step = _setup(db_session)

    text = client.get(f"/learning-steps/{step.id}/handoff").json()["text"]

    assert text.startswith("# Tave 논문 스터디 — 2주차 — SAM 체크리스트 만들기")
    assert "매주 논문 읽고 발표" in text
    assert "- 단계: 2주차 — SAM (2/2번째)" in text
    assert "- 마감: 2026-09-26" in text
    assert "- 끝낸 이전 단계: 1주차 — CLIP" in text
    assert "- 이 단계 체크리스트: 2개 중 1개 체크" in text
    assert "  - [ ] `SamPredictor` 데모 실행" in text
    assert "논문 정독" not in text.split("남은 항목:")[1].split("자료 링크")[0]
    assert "SAM 저장소 — https://github.com/facebookresearch/segment-anything" in text
    assert "<li> 체크 항목" in text


def test_missing_fields_say_so_instead_of_guessing(client, db_session):
    path = models.LearningPath(title="coding rehab")
    db_session.add(path)
    db_session.flush()
    step = models.LearningStep(learning_path_id=path.id, title="파이썬 기초", position=0)
    db_session.add(step)
    db_session.commit()

    text = client.get(f"/learning-steps/{step.id}/handoff").json()["text"]

    assert "경로 설명 없음" in text
    assert "- 마감: 없음" in text
    assert "- 이 단계 체크리스트: 아직 없음" in text
