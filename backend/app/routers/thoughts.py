"""생각 · 고민 · 아이디어 API.

여러 세션에 흩어지는 것을 한 곳에 적어 둔다. 수업 들으며 나온 생각,
공부하다 떠오른 아이디어가 그 대화 안에서 끝나지 않게.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import reminder as reminder_service
from ..services import thought as thought_service
from ._common import delete_instance, get_or_404

router = APIRouter(tags=["thoughts"])


@router.get("/thoughts")
def list_thoughts(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """적어 둔 것 전부. 열린 고민이 맨 위."""
    return thought_service.build_list(db, status)


@router.post("/thoughts", status_code=201)
def create_thought(
    payload: schemas.ThoughtCreate,
    db: Session = Depends(get_db),
):
    """한 줄 적어 둔다.

    수현: "대학원을 갈지 말지 고민하는 거 얘는 모르잖아." 앱이 모르면
    그 고민에 쓸 데이터를 들고 있어도 만날 일이 없다.
    """
    return thought_service.create(
        db, payload.kind, payload.body, payload.source
    )


@router.post("/thoughts/{thought_id}/decide")
def decide_thought(
    thought_id: int,
    payload: schemas.ThoughtDecide,
    db: Session = Depends(get_db),
):
    """정했다고 표시한다. 무엇으로 정했는지 같이 적는다.

    비워서 보내면 다시 연다 — 되돌릴 데가 없으면 닫기를 망설이게 된다.
    """
    thought = get_or_404(db, models.Thought, thought_id, "Thought")

    return thought_service.decide(db, thought, payload.decision)


@router.delete("/thoughts/{thought_id}")
def remove_thought(thought_id: int, db: Session = Depends(get_db)):
    thought = get_or_404(db, models.Thought, thought_id, "Thought")

    return delete_instance(thought, db)


# --------------------------------
# 알리미 — 날짜가 있는 것
# --------------------------------

@router.get("/reminders")
def list_reminders(db: Session = Depends(get_db)):
    """앞으로 2주간 알릴 것 전부.

    수현: "오늘 마감 · 역량검사 대비 (10/18 일) 이런 것도
    알리미처럼 넣으려고."

    공고 마감 · 지원서 마감 · 시험 · 학습 마감은 앱이 이미 안다.
    흩어져 있던 것을 모으고, 앱이 모르는 것만 사람이 적는다.
    """
    return reminder_service.gather(db)


@router.post("/reminders", status_code=201)
def create_reminder(
    payload: schemas.ReminderCreate,
    db: Session = Depends(get_db),
):
    """앱이 모르는 알림을 적는다 — "친구에게 논문 전달" 같은 것."""
    return reminder_service.create(
        db, payload.title, payload.due, payload.at, payload.note
    )


@router.post("/reminders/{reminder_id}/done")
def finish_reminder(reminder_id: int, db: Session = Depends(get_db)):
    """지나간 것으로 표시한다. 판에서 내려간다."""
    row = get_or_404(db, models.Reminder, reminder_id, "Reminder")
    row.done = True
    db.commit()

    return {"id": row.id, "done": True}


@router.delete("/reminders/{reminder_id}")
def remove_reminder(reminder_id: int, db: Session = Depends(get_db)):
    row = get_or_404(db, models.Reminder, reminder_id, "Reminder")

    return delete_instance(row, db)
