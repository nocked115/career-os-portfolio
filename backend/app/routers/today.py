"""Today Plan API (Phase 1).

기존 `GET /today` 는 main.py 에 그대로 두고 건드리지 않는다.
계획을 만들고 체크하는 것은 여기서 한다.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import today as today_service
from ..services import why as why_service
from ._common import get_or_404

router = APIRouter(prefix="/today", tags=["today"])


@router.get("/plan")
def get_today_plan(
    available_minutes: int = Query(
        today_service.DEFAULT_AVAILABLE_MINUTES, ge=0, le=1440
    ),
    intensity: str = today_service.DEFAULT_INTENSITY,
    db: Session = Depends(get_db),
):
    """오늘 저장된 계획. 아직 만들지 않았으면 빈 목록."""
    return today_service.build_plan(
        db,
        available_minutes=available_minutes,
        intensity_name=intensity,
    )


@router.post("/plan")
def create_today_plan(
    available_minutes: int = Query(
        today_service.DEFAULT_AVAILABLE_MINUTES, ge=0, le=1440
    ),
    intensity: str = today_service.DEFAULT_INTENSITY,
    db: Session = Depends(get_db),
):
    """오늘 계획을 만든다. 다시 부르면 아직 안 한 것만 새로 짠다.

    이미 끝낸 일은 지우지 않는다.
    """
    if intensity not in today_service.INTENSITY:
        raise HTTPException(
            status_code=422,
            detail=(
                "intensity 는 "
                + " / ".join(today_service.INTENSITY)
                + " 중 하나여야 합니다"
            ),
        )

    return today_service.generate_plan(
        db,
        available_minutes=available_minutes,
        intensity_name=intensity,
    )


@router.get("/why")
def get_today_why(
    available_minutes: int = Query(
        today_service.DEFAULT_AVAILABLE_MINUTES, ge=0, le=1440
    ),
    intensity: str = today_service.DEFAULT_INTENSITY,
    db: Session = Depends(get_db),
):
    """오늘 계획이 왜 이렇게 나왔는지.

    새로 계산하지 않는다. 각 서비스가 이미 내놓는 값을 모은다.
    데이터가 없는 입력은 available=false 로 표시해서
    무엇을 못 봤는지도 같이 보여준다.
    """
    return why_service.build_why(
        db,
        available_minutes=available_minutes,
        intensity_name=intensity,
    )


@router.get("/intensities")
def list_intensities():
    """선택할 수 있는 강도와 그 의미."""
    return {
        "intensities": [
            {
                "key": key,
                "label": value["label"],
                "max_tasks": value["max_tasks"],
                "min_block": value["min_block"],
                "max_block": value["max_block"],
            }
            for key, value in today_service.INTENSITY.items()
        ]
    }


@router.get("/deadlines")
def get_deadlines(db: Session = Depends(get_db)):
    """다가오는 마감. 지난 것은 빼고 가까운 순으로."""
    return {"deadlines": today_service.collect_deadlines(db)}


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: int,
    body: schemas.TaskCompleteRequest | None = None,
    db: Session = Depends(get_db),
):
    """완료 처리. 학습 단계라면 실제 진행도까지, 루틴이면 그날 기록까지 남긴다."""
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    return today_service.complete_task(db, task, count=body.count if body else None)


@router.post("/tasks/{task_id}/revive")
def revive_task(task_id: int, db: Session = Depends(get_db)):
    """사흘 넘게 밀린 일을 "그래도 하겠다" 고 되살린다.

    "이건 안 할 건가요?" 는 두 답이 다 가능해야 질문이다. 치우는
    길만 있으면 그건 묻는 게 아니라 버리는 것이다.

    나이를 오늘로 되돌린다. 그러면 다시 이월 후보가 되고, 또 사흘을
    미루면 다시 물어본다.
    """
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    task.carried_from = date.today()

    db.commit()
    db.refresh(task)

    return today_service.serialize_task(task)


@router.post("/tasks/{task_id}/skip")
def skip_task(task_id: int, db: Session = Depends(get_db)):
    """오늘은 넘긴다. 이월되지 않고 여기서 끝난다."""
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    task.status = "skipped"
    db.commit()
    db.refresh(task)

    return today_service.serialize_task(task)
