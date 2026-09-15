"""시장 신호 API (Mission 023)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import market as market_service

router = APIRouter(prefix="/analytics", tags=["market"])


@router.get("/market-signals")
def get_market_signals(
    limit: int | None = None,
    db: Session = Depends(get_db),
):
    """수집된 기회에서 계산한 스킬별 수요와 추세.

    스냅샷이 하나뿐이면 추세는 unknown 이다.
    비교할 과거가 없는데 화살표를 그리지 않는다.
    """
    return market_service.build_signals_with_trend(db, limit=limit)


@router.post("/market-snapshots")
def capture_market_snapshot(db: Session = Depends(get_db)):
    """현재 수요를 스냅샷으로 남긴다.

    보통은 자동화가 수집 직후에 부른다. 수동 호출도 가능하다.
    """
    saved = market_service.capture_snapshot(db)

    return {
        "captured_rows": saved,
        "total_opportunities": market_service.count_opportunities(db),
    }
