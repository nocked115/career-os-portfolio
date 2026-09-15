"""데이터 통째로 내보내기 / 불러오기.

배포본의 볼륨 안에 있는 SQLite 파일은 밖에서 만질 수 없다.
그래서 옮기는 길도 백업하는 길도 여기 하나뿐이다.

인증은 미들웨어가 이미 걸어둔다 (auth.py). 운영에서는 이 두
경로도 다른 경로와 똑같이 막힌다.
"""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import transfer as transfer_service

router = APIRouter(prefix="/transfer", tags=["transfer"])

# 불러오기는 기존 데이터를 전부 지운다. 오타 한 번에 경력 기록이
# 날아가면 안 되므로, 무엇을 하는지 적어야 실행된다.
CONFIRM_WORD = "REPLACE"


@router.get("/export")
def export_everything(db: Session = Depends(get_db)) -> dict[str, Any]:
    """지금 DB 를 통째로 뜬다. 그대로 저장하면 백업이다."""
    return transfer_service.dump(db)


@router.post("/import")
def import_everything(
    payload: dict[str, Any] = Body(...),
    confirm: str = Query(
        ...,
        description=(
            f"기존 데이터를 전부 지우고 대체한다. '{CONFIRM_WORD}' 라고 "
            "적어야 실행된다."
        ),
    ),
    allow_schema_mismatch: bool = Query(False),
    allow_stale: bool = Query(
        False,
        description=(
            "받는 쪽에 더 새로운 작업이 있어도 덮어쓴다. "
            "그 작업은 사라지고 되돌릴 수 없다."
        ),
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """내보낸 파일로 현재 데이터를 대체한다."""
    if confirm != CONFIRM_WORD:
        raise HTTPException(
            status_code=400,
            detail=(
                "이 요청은 기존 데이터를 전부 지웁니다. "
                f"실행하려면 confirm={CONFIRM_WORD} 를 붙이세요."
            ),
        )

    try:
        result = transfer_service.load(
            db,
            payload,
            allow_schema_mismatch=allow_schema_mismatch,
            allow_stale=allow_stale,
        )
    except transfer_service.StaleFile as error:
        # 형식은 맞는데 타이밍이 틀렸다. 409 로 구분해야 화면과
        # 사람이 "덮어쓸까요?" 를 물어볼 수 있다.
        raise HTTPException(status_code=409, detail=str(error)) from error
    except transfer_service.TransferError as error:
        # 형식이나 스키마가 안 맞는 것은 서버 잘못이 아니다.
        raise HTTPException(status_code=400, detail=str(error)) from error

    return result
