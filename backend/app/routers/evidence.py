"""증거 집계 API (Phase 1).

Career OS 홈의 별 개수가 여기서 나온다.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import evidence as evidence_service

router = APIRouter(prefix="/analytics", tags=["evidence"])


@router.get("/evidence")
def get_evidence(db: Session = Depends(get_db)):
    """지금까지 쌓은 증거의 개수와 구성.

    총합만이 아니라 무엇으로 이루어졌는지 함께 돌려준다.
    개수가 0이면 0이다. 비어 있다는 것도 정확한 상태다.
    """
    return evidence_service.build_evidence(db)
