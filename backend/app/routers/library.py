"""My Learning Library API (Phase 2)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import library as library_service
from ._common import apply_update, delete_instance, get_or_404

router = APIRouter(tags=["library"])


# --------------------------------
# 라이브러리
# --------------------------------

@router.get("/library")
def get_library(
    resource_type: str | None = None,
    ownership: str | None = None,
    skill_id: int | None = None,
    db: Session = Depends(get_db),
):
    """내가 가진 것과 저장해둔 것."""
    return {
        "summary": library_service.summarize(db),
        "hot": library_service.build_hot(db),
        "items": library_service.list_library(
            db,
            resource_type=resource_type,
            ownership=ownership,
            skill_id=skill_id,
        ),
    }


# --------------------------------
# 서가 · 오늘 학습에 꺼내기
# --------------------------------

@router.post("/resources/{resource_id}/shelf")
def move_resource_shelf(
    resource_id: int,
    to: str = Query(..., description="in_progress · queued · on_hold · completed"),
    db: Session = Depends(get_db),
):
    """자료를 지금 학습 · 다음 학습 · 보류 · 완료 서가로 옮긴다."""
    if to not in library_service.SHELVES:
        raise HTTPException(
            status_code=422,
            detail="서가는 지금 학습 · 다음 학습 · 보류 · 완료 중 하나여야 합니다.",
        )

    resource = get_or_404(
        db, models.LearningResource, resource_id, "Learning resource"
    )

    return library_service.set_shelf(db, resource, to)


@router.post("/resources/{resource_id}/add-to-plan")
def add_resource_to_plan(
    resource_id: int,
    minutes: int | None = Query(None, ge=5, le=480),
    db: Session = Depends(get_db),
):
    """이 자료의 다음 챕터를 오늘 계획에 올리고 '지금 학습' 으로 옮긴다."""
    resource = get_or_404(
        db, models.LearningResource, resource_id, "Learning resource"
    )

    return library_service.add_to_plan(db, resource, minutes)


# --------------------------------
# 조각 (Segment)
# --------------------------------

@router.get(
    "/resources/{resource_id}/segments",
    response_model=list[schemas.SegmentResponse],
)
def list_segments(resource_id: int, db: Session = Depends(get_db)):
    resource = get_or_404(
        db, models.LearningResource, resource_id, "Learning resource"
    )

    return resource.segments


@router.post(
    "/resources/{resource_id}/segments",
    response_model=schemas.SegmentResponse,
    status_code=201,
)
def create_segment(
    resource_id: int,
    payload: schemas.SegmentCreate,
    db: Session = Depends(get_db),
):
    """자료를 오늘 소비할 수 있는 크기로 쪼갠다.

    "책 한 권" 이 아니라 "3장 15분" 이 단위다.
    """
    resource = get_or_404(
        db, models.LearningResource, resource_id, "Learning resource"
    )

    duplicate = next(
        (s for s in resource.segments if s.position == payload.position),
        None,
    )

    if duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail=f"position {payload.position} 은(는) 이미 사용 중입니다",
        )

    segment = models.LearningResourceSegment(
        learning_resource_id=resource.id,
        **payload.model_dump(),
    )

    db.add(segment)
    db.commit()
    db.refresh(segment)

    return segment


@router.patch(
    "/segments/{segment_id}",
    response_model=schemas.SegmentResponse,
)
def update_segment(
    segment_id: int,
    payload: schemas.SegmentUpdate,
    db: Session = Depends(get_db),
):
    segment = get_or_404(
        db, models.LearningResourceSegment, segment_id, "Segment"
    )

    return apply_update(segment, payload, db)


@router.delete("/segments/{segment_id}")
def delete_segment(segment_id: int, db: Session = Depends(get_db)):
    segment = get_or_404(
        db, models.LearningResourceSegment, segment_id, "Segment"
    )

    return delete_instance(segment, db)


@router.post("/segments/{segment_id}/complete")
def complete_segment(segment_id: int, db: Session = Depends(get_db)):
    """이 조각을 끝냈다. 자료의 모든 조각이 끝나면 자료도 완료가 된다."""
    segment = get_or_404(
        db, models.LearningResourceSegment, segment_id, "Segment"
    )

    return library_service.complete_segment(db, segment)


# --------------------------------
# 선별
# --------------------------------

@router.get("/library/selection")
def select_library_for_today(
    available_minutes: int = Query(120, ge=0, le=1440),
    db: Session = Depends(get_db),
):
    """라이브러리 전체에서 오늘 필요한 것만 고른다.

    치운 것을 개수와 이유까지 함께 돌려준다.
    "63개" 를 조용히 감추면 그건 선별이 아니라 필터다.
    """
    return library_service.select_for_today(db, available_minutes)


@router.get("/learning-steps/{step_id}/selection")
def select_for_step(
    step_id: int,
    available_minutes: int = Query(45, ge=0, le=1440),
    db: Session = Depends(get_db),
):
    """이 단계에 대해 오늘 볼 것만 고른다.

    고른 것과 **치운 것을 함께** 돌려준다.
    치운 것을 숨기면 선별했다는 증거가 사라진다.
    """
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    return library_service.select_for_step(db, step, available_minutes)
