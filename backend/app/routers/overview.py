"""한눈에 보기 API — 지금 상태의 요약. 행동은 Today 에서."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import overview as overview_service

router = APIRouter(tags=["overview"])


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    """목표 · 준비도 · 이번 주 실행 · 영역별 요약 · 다음 행동."""
    return overview_service.build_overview(db)
