"""PROVE — 프로젝트를 증거로 바꾸는 흐름 (Phase 4)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import proof as proof_service
from ._common import apply_update, get_or_404

router = APIRouter(tags=["proof"])


@router.get("/projects/{project_id}/evidence")
def get_evidence_suggestions(project_id: int, db: Session = Depends(get_db)):
    """이 프로젝트가 증명하는 것과, 다음에 할 일.

    완료되지 않았으면 "아직 아니다" 라고 답한다.
    """
    project = get_or_404(db, models.Project, project_id, "Project")

    return proof_service.build_suggestions(db, project)


@router.patch(
    "/projects/{project_id}",
    response_model=schemas.ProjectResponse,
)
def update_project(
    project_id: int,
    payload: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
):
    """프로젝트 수정. Phase 4 이전에는 수정 수단이 아예 없었다."""
    project = get_or_404(db, models.Project, project_id, "Project")

    return apply_update(project, payload, db)


@router.post(
    "/projects/{project_id}/to-experience",
    response_model=schemas.ExperienceResponse,
)
def convert_to_experience(project_id: int, db: Session = Depends(get_db)):
    """프로젝트를 Experience Bank 로 옮긴다.

    내용을 복사할 뿐 새로 지어내지 않는다.
    이미 있으면 그것을 돌려준다.
    """
    project = get_or_404(db, models.Project, project_id, "Project")

    experience, _ = proof_service.to_experience(db, project)

    return experience


@router.post("/portfolio-entries/{entry_id}/resume-bullet")
def generate_resume_bullet(entry_id: int, db: Session = Depends(get_db)):
    """이력서 한 줄 초안을 만들어 저장한다.

    저장된 내용에서만 조립한다.
    재료가 없으면 문장 대신 무엇이 비었는지 알려준다.
    """
    entry = get_or_404(
        db, models.PortfolioEntry, entry_id, "Portfolio entry"
    )

    return proof_service.save_resume_bullet(db, entry)
