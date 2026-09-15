"""Calendar API (Phase 5.6).

학교 시간표를 가져오지 않는다. 직접 넣는다.
가져오기는 파일 형식과 학교마다 다른 규칙에 묶이고, 그러다 보면
"내 일정" 이 아니라 "학교가 아는 내 일정" 이 된다.
"""

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import calendar as calendar_service
from ..services import profile as profile_service
from ._common import apply_update, delete_instance, get_or_404

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/blocks")
def list_blocks(
    weekday: int | None = Query(default=None, ge=0, le=6),
    db: Session = Depends(get_db),
):
    """등록한 일정 전체. weekday 를 주면 그 요일만."""
    return {"blocks": calendar_service.list_blocks(db, weekday)}


@router.post("/blocks")
def create_block(
    payload: schemas.CalendarBlockCreate,
    db: Session = Depends(get_db),
):
    block = models.CalendarBlock(**payload.model_dump())

    db.add(block)
    db.commit()
    db.refresh(block)

    return calendar_service.serialize(block)


@router.patch("/blocks/{block_id}")
def update_block(
    block_id: int,
    payload: schemas.CalendarBlockUpdate,
    db: Session = Depends(get_db),
):
    block = get_or_404(db, models.CalendarBlock, block_id, "Calendar block")

    return calendar_service.serialize(apply_update(block, payload, db))


@router.delete("/blocks/{block_id}")
def delete_block(block_id: int, db: Session = Depends(get_db)):
    block = get_or_404(db, models.CalendarBlock, block_id, "Calendar block")

    return delete_instance(block, db)


@router.get("/day")
def get_day(
    date: date_type | None = None,
    db: Session = Depends(get_db),
):
    """오늘 몇 분이 비었고, 그중 얼마를 쓰자고 제안하는가."""
    return calendar_service.build_day(db, date)


@router.get("/week")
def get_week(db: Session = Depends(get_db)):
    """요일별 일정과 빈 시간. 매주 반복되는 것만."""
    return calendar_service.build_week(db)


@router.get("/month")
def get_month(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
):
    """한 달. 매주 일정 · 하루 일정 · 지원서와 공고 마감을 한 장에."""
    return calendar_service.build_month(db, year, month)


@router.patch("/settings")
def update_settings(
    payload: schemas.CalendarSettingsUpdate,
    db: Session = Depends(get_db),
):
    """활동 시간대와 하루 상한."""
    profile = profile_service.get_profile(db)

    apply_update(profile, payload, db)

    return calendar_service.build_week(db)
