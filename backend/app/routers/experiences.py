"""Experience Bank / Portfolio API (SPEC 11~12장)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import proof as proof_service
from ._common import apply_update, delete_instance, ensure_exists, get_or_404

router = APIRouter(tags=["experiences"])


# --------------------------------
# Experience Bank
# --------------------------------

@router.post(
    "/experiences",
    response_model=schemas.ExperienceResponse,
    status_code=201,
)
def create_experience(
    payload: schemas.ExperienceCreate,
    db: Session = Depends(get_db),
):
    ensure_exists(db, models.Project, payload.project_id, "Project")

    experience = models.Experience(**payload.model_dump())

    db.add(experience)
    db.commit()
    db.refresh(experience)

    return experience


@router.get(
    "/experiences",
    response_model=list[schemas.ExperienceResponse],
)
def list_experiences(
    experience_type: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Experience)

    if experience_type is not None:
        query = query.filter(
            models.Experience.experience_type == experience_type
        )

    return query.order_by(models.Experience.created_at.desc()).all()


# {experience_id} 보다 먼저 둔다. 뒤에 두면 "usage" 를 id 로 읽으려다 422 가 난다.
@router.get("/experiences/usage")
def get_experience_usage(db: Session = Depends(get_db)):
    """경험마다 연결된 프로젝트 · 포트폴리오 · 매칭한 지원서 · 비어 있는 칸."""
    return proof_service.experience_usage(db)


@router.get(
    "/experiences/{experience_id}",
    response_model=schemas.ExperienceResponse,
)
def get_experience(
    experience_id: int,
    db: Session = Depends(get_db),
):
    return get_or_404(db, models.Experience, experience_id, "Experience")


@router.patch(
    "/experiences/{experience_id}",
    response_model=schemas.ExperienceResponse,
)
def update_experience(
    experience_id: int,
    payload: schemas.ExperienceUpdate,
    db: Session = Depends(get_db),
):
    experience = get_or_404(
        db,
        models.Experience,
        experience_id,
        "Experience",
    )

    ensure_exists(db, models.Project, payload.project_id, "Project")

    return apply_update(experience, payload, db)


@router.delete("/experiences/{experience_id}")
def delete_experience(
    experience_id: int,
    db: Session = Depends(get_db),
):
    experience = get_or_404(
        db,
        models.Experience,
        experience_id,
        "Experience",
    )

    return delete_instance(experience, db)


# --------------------------------
# Experience <-> Skill
# --------------------------------

@router.post("/experiences/{experience_id}/skills/{skill_id}")
def link_skill_to_experience(
    experience_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
):
    experience = get_or_404(
        db,
        models.Experience,
        experience_id,
        "Experience",
    )

    skill = get_or_404(db, models.Skill, skill_id, "Skill")

    if skill not in experience.skills:
        experience.skills.append(skill)
        db.commit()

    return {"message": f"{skill.name} linked to {experience.title}"}


@router.delete("/experiences/{experience_id}/skills/{skill_id}")
def unlink_skill_from_experience(
    experience_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
):
    experience = get_or_404(
        db,
        models.Experience,
        experience_id,
        "Experience",
    )

    skill = get_or_404(db, models.Skill, skill_id, "Skill")

    if skill in experience.skills:
        experience.skills.remove(skill)
        db.commit()

    return {"message": f"{skill.name} unlinked from {experience.title}"}


@router.get(
    "/experiences/{experience_id}/skills",
    response_model=list[schemas.SkillResponse],
)
def list_experience_skills(
    experience_id: int,
    db: Session = Depends(get_db),
):
    experience = get_or_404(
        db,
        models.Experience,
        experience_id,
        "Experience",
    )

    return experience.skills


# --------------------------------
# Portfolio
# --------------------------------

@router.post(
    "/portfolio-entries",
    response_model=schemas.PortfolioEntryResponse,
    status_code=201,
)
def create_portfolio_entry(
    payload: schemas.PortfolioEntryCreate,
    db: Session = Depends(get_db),
):
    ensure_exists(db, models.Experience, payload.experience_id, "Experience")
    ensure_exists(db, models.Project, payload.project_id, "Project")

    entry = models.PortfolioEntry(**payload.model_dump())

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry


@router.get(
    "/portfolio-entries",
    response_model=list[schemas.PortfolioEntryResponse],
)
def list_portfolio_entries(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.PortfolioEntry)

    if status is not None:
        query = query.filter(models.PortfolioEntry.status == status)

    return query.order_by(models.PortfolioEntry.display_order).all()


@router.get(
    "/portfolio-entries/{entry_id}",
    response_model=schemas.PortfolioEntryResponse,
)
def get_portfolio_entry(
    entry_id: int,
    db: Session = Depends(get_db),
):
    return get_or_404(
        db,
        models.PortfolioEntry,
        entry_id,
        "Portfolio entry",
    )


@router.patch(
    "/portfolio-entries/{entry_id}",
    response_model=schemas.PortfolioEntryResponse,
)
def update_portfolio_entry(
    entry_id: int,
    payload: schemas.PortfolioEntryUpdate,
    db: Session = Depends(get_db),
):
    entry = get_or_404(
        db,
        models.PortfolioEntry,
        entry_id,
        "Portfolio entry",
    )

    ensure_exists(db, models.Experience, payload.experience_id, "Experience")
    ensure_exists(db, models.Project, payload.project_id, "Project")

    return apply_update(entry, payload, db)


@router.delete("/portfolio-entries/{entry_id}")
def delete_portfolio_entry(
    entry_id: int,
    db: Session = Depends(get_db),
):
    entry = get_or_404(
        db,
        models.PortfolioEntry,
        entry_id,
        "Portfolio entry",
    )

    return delete_instance(entry, db)


@router.post(
    "/experiences/{experience_id}/portfolio-entry",
    response_model=schemas.PortfolioEntryResponse,
    status_code=201,
)
def promote_experience_to_portfolio(
    experience_id: int,
    db: Session = Depends(get_db),
):
    """Experience 를 Portfolio 항목으로 승격한다 (SPEC 12장).

    내용을 그대로 복사해서 초안을 만들고, 이후 수정은 PATCH 로 한다.
    """
    experience = get_or_404(
        db,
        models.Experience,
        experience_id,
        "Experience",
    )

    entry = models.PortfolioEntry(
        title=experience.title,
        short_description=experience.short_description,
        problem=experience.problem,
        role=experience.role,
        actions=experience.actions,
        results=experience.results,
        technologies=experience.technologies,
        github_url=experience.github_url,
        demo_url=experience.demo_url,
        status="draft",
        experience_id=experience.id,
        project_id=experience.project_id,
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry
