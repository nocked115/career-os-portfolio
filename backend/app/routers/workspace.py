"""Application Workspace API (Phase 5).

JD 분석 · 경험 자동 매칭 · 상태 전이 · 자소서 작성 지원.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..services import application as application_service
from ..services import jd as jd_service
from ._common import get_or_404

router = APIRouter(tags=["workspace"])


# --------------------------------
# JD 분석
# --------------------------------

@router.get("/applications/{application_id}/analysis")
def analyze(application_id: int, db: Session = Depends(get_db)):
    """공고를 분석하고 쓸 경험을 고른다.

    등록된 스킬 이름을 본문에서 찾는 방식이다.
    한계를 응답의 notes 에 그대로 적는다.
    """
    application = get_or_404(
        db, models.Application, application_id, "Application"
    )

    return jd_service.analyze_application(db, application)


@router.post("/applications/{application_id}/auto-match")
def auto_match(application_id: int, db: Session = Depends(get_db)):
    """분석 결과를 경험 매칭으로 저장한다.

    사람이 써둔 메모는 덮어쓰지 않는다.
    """
    application = get_or_404(
        db, models.Application, application_id, "Application"
    )

    return jd_service.auto_match(db, application)


# --------------------------------
# 상태 전이
# --------------------------------

@router.get("/applications/{application_id}/transitions")
def get_transitions(application_id: int, db: Session = Depends(get_db)):
    """지금 상태에서 갈 수 있는 곳."""
    application = get_or_404(
        db, models.Application, application_id, "Application"
    )

    return {
        "current": application.status,
        "allowed": application_service.allowed_next(application.status),
        "is_terminal": application.status in application_service.TERMINAL,
    }


@router.post("/applications/{application_id}/move")
def move(
    application_id: int,
    status: str,
    force: bool = Query(
        False,
        description="순서를 건너뛴다. 잘못 누른 것을 되돌릴 때만 쓴다.",
    ),
    db: Session = Depends(get_db),
):
    """상태를 옮긴다. 규칙에 없는 이동은 막는다."""
    application = get_or_404(
        db, models.Application, application_id, "Application"
    )

    if status not in application_service.TRANSITIONS:
        raise HTTPException(
            status_code=422,
            detail=f"알 수 없는 상태입니다: {status}",
        )

    if not force and not application_service.can_move(
        application.status, status
    ):
        raise HTTPException(
            status_code=409,
            detail=application_service.describe_transition(
                application.status, status
            ),
        )

    previous = application.status
    application.status = status

    db.commit()
    db.refresh(application)

    return {
        "application_id": application.id,
        "from": previous,
        "to": status,
        "forced": force,
        "allowed_next": application_service.allowed_next(status),
    }


# --------------------------------
# 자소서
# --------------------------------

@router.get("/cover-letter-questions/{question_id}/outline")
def outline(question_id: int, db: Session = Depends(get_db)):
    """이 문항에 쓸 구조를 잡아준다.

    문장을 만들지 않는다. 어떤 경험을 어떤 순서로 쓸지만 정한다.
    """
    question = get_or_404(
        db, models.CoverLetterQuestion, question_id, "Cover letter question"
    )

    return application_service.build_outline(
        db, question.application, question
    )


@router.post("/cover-letter-questions/{question_id}/review")
def review(
    question_id: int,
    draft: str = "",
    db: Session = Depends(get_db),
):
    """쓴 글을 기계적으로 점검한다.

    글자 수와 근거 유무만 본다. 문체와 설득력은 판단하지 않는다.
    """
    question = get_or_404(
        db, models.CoverLetterQuestion, question_id, "Cover letter question"
    )

    return application_service.review_answer(db, question, draft)
