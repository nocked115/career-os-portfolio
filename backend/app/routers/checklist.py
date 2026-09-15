"""학습 단계 체크리스트 API.

붙여넣기 → 미리보기(parse) → 고쳐서 저장(import) 의 두 번 호출이다.
parse 는 저장하지 않고 링크도 열지 않는다.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import checklist as checklist_service
from ..services import checklist_parser
from ..services import learning as learning_service
from ._common import get_or_404

router = APIRouter(tags=["checklist"])


@router.post("/checklists/parse")
def parse_checklist(body: schemas.ChecklistParseRequest):
    """붙여넣은 HTML · Markdown · 줄글에서 제목 · 묶음 · 항목 · 링크를 고른다."""
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="붙여넣은 내용이 비어 있어요.")

    return checklist_parser.parse_checklist(body.text)


@router.get("/learning-steps/{step_id}/handoff")
def get_step_handoff(step_id: int, db: Session = Depends(get_db)):
    """다른 세션에 붙여넣을 텍스트 — 트랙 설명 · 이번 단계 · 진행 · 체크리스트 형식."""
    from ..services import handoff as handoff_service

    step = get_or_404(db, models.LearningStep, step_id, "Learning step")
    return {"text": handoff_service.build_step_handoff(step)}


@router.get("/learning-steps/{step_id}/checklist")
def get_checklist(step_id: int, db: Session = Depends(get_db)):
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")
    return checklist_service.build_checklist(step)


@router.post("/learning-steps/{step_id}/checklist/import")
def import_checklist(
    step_id: int,
    body: schemas.ChecklistImport,
    db: Session = Depends(get_db),
):
    """미리보기에서 고친 구조를 이 단계에 붙인다 (replace 면 바꾼다)."""
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    try:
        added = checklist_service.import_structured(
            db, step, body.sections, body.links, replace=body.replace
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    db.commit()
    db.refresh(step)

    return {"added": added, "checklist": checklist_service.build_checklist(step)}


@router.post("/learning-paths/{path_id}/checklist-steps", status_code=201)
def create_step_from_checklist(
    path_id: int,
    body: schemas.ChecklistStepCreate,
    db: Session = Depends(get_db),
):
    """체크리스트 한 장을 경로의 새 단계로 — "2주차" 를 통째로 넣을 때."""
    path = get_or_404(db, models.LearningPath, path_id, "Learning path")

    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="단계 이름을 적어 주세요.")

    if not any(section.items for section in body.sections):
        raise HTTPException(status_code=400, detail="저장할 체크 항목이 없어요.")

    step = models.LearningStep(
        learning_path_id=path.id,
        title=title[:200],
        position=max((item.position for item in path.steps), default=-1) + 1,
        estimated_minutes=body.estimated_minutes,
        due_date=body.due_date,
    )
    db.add(step)
    db.flush()

    added = checklist_service.import_structured(db, step, body.sections, body.links)

    db.commit()
    db.refresh(step)
    learning_service.recalculate_path_progress(db, path)

    return {
        "step_id": step.id,
        "title": step.title,
        "added": added,
        "checklist": checklist_service.build_checklist(step),
    }


@router.post("/learning-steps/{step_id}/checklist", status_code=201)
def add_checklist_item(
    step_id: int,
    body: schemas.ChecklistItemCreate,
    db: Session = Depends(get_db),
):
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    item = checklist_service.add_item(
        db, step, text=body.text.strip(), section=body.section.strip(),
        kind=body.kind, url=body.url.strip(),
    )
    db.commit()
    db.refresh(step)

    return {
        "item": checklist_service.serialize_item(item),
        "checklist": checklist_service.build_checklist(step),
    }


@router.patch("/checklist-items/{item_id}")
def update_checklist_item(
    item_id: int,
    body: schemas.ChecklistItemUpdate,
    db: Session = Depends(get_db),
):
    item = get_or_404(db, models.LearningChecklistItem, item_id, "Checklist item")
    step = item.learning_step
    started = False

    if body.text is not None:
        item.text = body.text.strip()

    if body.done is not None:
        if item.kind != "task":
            raise HTTPException(status_code=400, detail="설명과 링크는 체크하는 항목이 아니에요.")
        started = checklist_service.set_done(step, item, body.done)

    db.commit()
    db.refresh(step)

    if started:
        learning_service.recalculate_path_progress(db, step.learning_path)

    return {
        "item": checklist_service.serialize_item(item),
        "step_status": step.status,
        "started": started,
        "checklist": checklist_service.build_checklist(step),
    }


@router.delete("/checklist-items/{item_id}")
def delete_checklist_item(item_id: int, db: Session = Depends(get_db)):
    item = get_or_404(db, models.LearningChecklistItem, item_id, "Checklist item")
    step = item.learning_step

    step.checklist.remove(item)
    db.delete(item)
    db.commit()
    db.refresh(step)

    return {"checklist": checklist_service.build_checklist(step)}
