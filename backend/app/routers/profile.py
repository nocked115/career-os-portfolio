"""Profile API.

Career OS 는 1인용이다. 그래서 목록도 인증도 없고, 프로필은
언제나 하나다. 없으면 빈 이름으로 만들어서 돌려준다.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services import profile as profile_service

router = APIRouter(tags=["profile"])


@router.get("/profile")
def get_profile(db: Session = Depends(get_db)):
    """나, 내 방향, 이번 주."""
    return profile_service.build_profile(db)


@router.patch("/profile")
def update_profile(
    payload: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
):
    """이름 · 링크를 바꾼다. 보낸 칸만 바뀐다."""
    profile_service.update_profile(db, **payload.model_dump(exclude_unset=True))

    return profile_service.build_profile(db)
