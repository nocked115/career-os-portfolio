"""Career Universe API (Phase 7).

홈 한 장에 필요한 것을 한 번에 준다. 조회 한 번에 화면이 완성돼야
궤도를 돌리는 동안 값이 늦게 도착하는 일이 없다.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import today as today_service
from ..services import universe as universe_service

router = APIRouter(tags=["universe"])


@router.get("/universe")
def get_universe(
    available_minutes: int = Query(
        today_service.DEFAULT_AVAILABLE_MINUTES, ge=0, le=1440
    ),
    db: Session = Depends(get_db),
):
    """나, 오늘, 증거, 그리고 천체 6개의 요약."""
    return universe_service.build_universe(
        db, available_minutes=available_minutes
    )
