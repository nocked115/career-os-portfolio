"""시장 신호 API (Mission 023)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import market as market_service
from ..services import vocabulary as vocabulary_service

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


@router.get("/skill-gaps")
def get_skill_gaps(db: Session = Depends(get_db)):
    """공고에 적혀 있는데 내 스킬 목록에 없는 도구.

    수요 계산은 등록된 스킬만 센다. 목록에 없으면 공고에 몇 번 나오든
    0건이라, 앱은 **모르는 도구를 영원히 모른다.** 순위표는 멀쩡해 보이는데
    정작 가장 많이 요구되는 것이 빠져 있을 수 있다.

    모집단은 수요 계산과 같다 (`market.demand_opportunities`). 달라지면
    여기 % 와 순위표 % 가 다른 뜻이 되어 나란히 못 놓는다.
    """
    return vocabulary_service.scan(db)


@router.get("/blocked-skills")
def get_blocked_skills(db: Session = Depends(get_db)):
    """자격 때문에 못 쓰는 공고가 스킬마다 몇 건인가.

    이 숫자가 없으면 "Computer Vision 수요 4건" 만 보이고, 그중 3건이
    석사 자리라는 건 안 보인다. 앱이 거꾸로 그걸 공부하라고 말하게 된다.
    """
    return {"skills": market_service.blocked_by_skill(db)}
