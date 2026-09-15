"""기간 회고 API.

하루치 계획은 Today 가 맡고, 여기는 "그래서 이번 달에 뭘 쌓았나" 를
맡는다.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services import review as review_service

router = APIRouter(prefix="/analytics", tags=["review"])


@router.get("/review")
def get_review(
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """한 달치 회고. 지정하지 않으면 이번 달."""
    today = date.today()

    if (year is None) != (month is None):
        raise HTTPException(
            status_code=422,
            detail="year 와 month 는 함께 주거나 함께 비워야 합니다",
        )

    return review_service.build_review(
        db, year or today.year, month or today.month
    )


@router.put("/review/reflection")
def save_reflection(
    payload: schemas.ReflectionUpdate,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """그 달의 스스로 평가 (1~5점과 세 줄). 아직 오지 않은 달은 적지 않는다."""
    today = date.today()

    if (year, month) > (today.year, today.month):
        raise HTTPException(status_code=400, detail="아직 오지 않은 달은 평가할 수 없어요.")

    return review_service.save_reflection(db, year, month, payload)


@router.get("/review/trend")
def get_review_trend(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """최근 몇 달. 한 달만 보면 늘었는지 줄었는지 알 수 없다."""
    return {"months": review_service.recent_months(db, count=months)}


@router.get("/activity")
def get_activity(
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """날마다 끝낸 것의 개수. 잔디 칸을 칠한다."""
    today = date.today()

    if (year is None) != (month is None):
        raise HTTPException(
            status_code=422,
            detail="year 와 month 는 함께 주거나 함께 비워야 합니다",
        )

    return review_service.build_activity(
        db, year or today.year, month or today.month
    )
