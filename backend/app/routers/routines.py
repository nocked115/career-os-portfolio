"""루틴 API — 정한 요일마다 하는 일과 그날의 기록."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import routine as routine_service
from ..services import today as today_service
from ._common import get_or_404

router = APIRouter(tags=["routines"])


def _check_path(db, path_id):
    if path_id is not None and db.get(models.LearningPath, path_id) is None:
        raise HTTPException(status_code=404, detail="연결할 학습 경로를 찾지 못했어요.")


def _weekdays(values) -> str:
    try:
        return routine_service.encode_weekdays(values)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/routines")
def list_routines(db: Session = Depends(get_db)):
    today = date.today()
    routines = db.query(models.Routine).order_by(models.Routine.id).all()

    return {
        "date": today,
        "routines": [routine_service.serialize(routine, today) for routine in routines],
        "daily_minutes": sum(
            routine.minutes for routine in routines if routine_service.is_due(routine, today)
        ),
    }


@router.post("/routines", status_code=201)
def create_routine(body: schemas.RoutineCreate, db: Session = Depends(get_db)):
    _check_path(db, body.learning_path_id)

    routine = models.Routine(
        title=body.title.strip(),
        minutes=body.minutes,
        weekdays=_weekdays(body.weekdays),
        target_count=body.target_count,
        unit_label=body.unit_label.strip(),
        learning_path_id=body.learning_path_id,
        link_url=body.link_url.strip(),
        note=body.note,
    )
    db.add(routine)
    db.commit()
    db.refresh(routine)

    return routine_service.serialize(routine, date.today())


@router.patch("/routines/{routine_id}")
def update_routine(
    routine_id: int,
    body: schemas.RoutineUpdate,
    db: Session = Depends(get_db),
):
    routine = get_or_404(db, models.Routine, routine_id, "Routine")
    changes = body.model_dump(exclude_unset=True)

    if "learning_path_id" in changes:
        _check_path(db, changes["learning_path_id"])
    if "weekdays" in changes:
        changes["weekdays"] = _weekdays(changes["weekdays"])
    if "title" in changes:
        changes["title"] = changes["title"].strip()
    if changes.get("link_url"):
        changes["link_url"] = changes["link_url"].strip()

    for field, value in changes.items():
        setattr(routine, field, value)

    db.commit()
    db.refresh(routine)

    return routine_service.serialize(routine, date.today())


@router.delete("/routines/{routine_id}")
def delete_routine(routine_id: int, db: Session = Depends(get_db)):
    """지운다. 아직 안 한 오늘 계획 항목은 치우고, 끝낸 기록은 남긴다."""
    routine = get_or_404(db, models.Routine, routine_id, "Routine")

    released = today_service.release_plan_tasks(
        db, models.DailyPlanTask.routine_id, routine.id
    )
    db.delete(routine)
    db.commit()

    return {"deleted": routine_id, "plan": released}


@router.put("/routines/{routine_id}/logs/{log_date}")
def set_routine_log(
    routine_id: int,
    log_date: date,
    body: schemas.RoutineLogUpdate,
    db: Session = Depends(get_db),
):
    """그날 기록을 고친다. done=false 면 기록을 지운다."""
    routine = get_or_404(db, models.Routine, routine_id, "Routine")

    if log_date > date.today():
        raise HTTPException(status_code=400, detail="아직 오지 않은 날은 기록할 수 없어요.")

    if body.done:
        routine_service.record(db, routine, log_date, body.count)
    else:
        routine_service.unrecord(db, routine, log_date)

    db.commit()
    db.refresh(routine)

    return routine_service.serialize(routine, date.today())
