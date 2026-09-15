"""Target Career API (Phase 1).

목표 직무는 모든 우선순위 계산의 기준점이다.
활성은 한 번에 하나이고, 바꿔도 이전 목표를 지우지 않는다.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import priority as priority_service
from ._common import apply_update, delete_instance, get_or_404

router = APIRouter(prefix="/target-careers", tags=["target career"])


def _deactivate_others(db, keep_id=None):
    """활성은 하나만. 나머지를 내린다."""
    query = db.query(models.TargetCareer).filter(
        models.TargetCareer.is_active.is_(True)
    )

    if keep_id is not None:
        query = query.filter(models.TargetCareer.id != keep_id)

    for other in query.all():
        other.is_active = False


@router.post("", response_model=schemas.TargetCareerResponse, status_code=201)
def create_target_career(
    payload: schemas.TargetCareerCreate,
    db: Session = Depends(get_db),
):
    target = models.TargetCareer(**payload.model_dump())

    db.add(target)
    db.flush()

    if target.is_active:
        _deactivate_others(db, keep_id=target.id)

    db.commit()
    db.refresh(target)

    return target


@router.get("", response_model=list[schemas.TargetCareerResponse])
def list_target_careers(db: Session = Depends(get_db)):
    return (
        db.query(models.TargetCareer)
        .order_by(models.TargetCareer.created_at.desc())
        .all()
    )


# 정적 경로는 "/{id}" 보다 먼저 선언해야 한다.
@router.get("/active")
def get_active_target_career(db: Session = Depends(get_db)):
    """지금 기준이 되는 목표 직무.

    없으면 404 가 아니라 null 을 돌려준다.
    "아직 정하지 않았다" 는 오류가 아니라 정상 상태다.
    """
    target = priority_service.get_active_target_career(db)

    if target is None:
        return {
            "target_career": None,
            "message": (
                "목표 직무가 아직 없습니다. "
                "정하면 학습 우선순위가 목표 기준으로 바뀝니다."
            ),
        }

    return {
        "target_career": {
            "id": target.id,
            "title": target.title,
            "description": target.description,
            "keywords": [
                k.strip() for k in (target.keywords or "").split(",") if k.strip()
            ],
            "target_date": target.target_date,
            "skills": [
                {"id": s.id, "name": s.name, "level": s.level}
                for s in target.skills
            ],
        },
        "message": None,
    }


@router.get("/{target_id}", response_model=schemas.TargetCareerResponse)
def get_target_career(target_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.TargetCareer, target_id, "Target career")


@router.patch("/{target_id}", response_model=schemas.TargetCareerResponse)
def update_target_career(
    target_id: int,
    payload: schemas.TargetCareerUpdate,
    db: Session = Depends(get_db),
):
    target = get_or_404(db, models.TargetCareer, target_id, "Target career")

    return apply_update(target, payload, db)


@router.delete("/{target_id}")
def delete_target_career(target_id: int, db: Session = Depends(get_db)):
    target = get_or_404(db, models.TargetCareer, target_id, "Target career")

    return delete_instance(target, db)


@router.post("/{target_id}/activate", response_model=schemas.TargetCareerResponse)
def activate_target_career(target_id: int, db: Session = Depends(get_db)):
    """이 목표를 기준으로 삼는다. 나머지는 자동으로 내려간다."""
    target = get_or_404(db, models.TargetCareer, target_id, "Target career")

    _deactivate_others(db, keep_id=target.id)
    target.is_active = True

    db.commit()
    db.refresh(target)

    return target


@router.get(
    "/{target_id}/skills",
    response_model=list[schemas.SkillResponse],
)
def list_target_career_skills(target_id: int, db: Session = Depends(get_db)):
    target = get_or_404(db, models.TargetCareer, target_id, "Target career")

    return target.skills


@router.post("/{target_id}/skills/{skill_id}")
def link_skill_to_target_career(
    target_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
):
    target = get_or_404(db, models.TargetCareer, target_id, "Target career")
    skill = get_or_404(db, models.Skill, skill_id, "Skill")

    if skill not in target.skills:
        target.skills.append(skill)
        db.commit()

    return {"message": f"{skill.name} linked to {target.title}"}


@router.delete("/{target_id}/skills/{skill_id}")
def unlink_skill_from_target_career(
    target_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
):
    target = get_or_404(db, models.TargetCareer, target_id, "Target career")
    skill = get_or_404(db, models.Skill, skill_id, "Skill")

    if skill in target.skills:
        target.skills.remove(skill)
        db.commit()

    return {"message": f"{skill.name} unlinked from {target.title}"}
