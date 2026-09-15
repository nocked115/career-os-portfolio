"""Opportunity API.

Job 은 그대로 두고, Opportunity 를 소스 독립적인 상위 개념으로 둔다.
legacy_job_id 로 기존 Job 과 연결할 수 있다 (SPEC 13~14장).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import opportunity as opportunity_service
from ..services import opportunity_map as map_service
from ..services import posting_parser
from ..services import today as today_service
from ._common import apply_update, delete_instance, ensure_exists, get_or_404

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.post(
    "",
    response_model=schemas.OpportunityResponse,
    status_code=201,
)
def create_opportunity(
    payload: schemas.OpportunityCreate,
    db: Session = Depends(get_db),
):
    ensure_exists(db, models.Job, payload.legacy_job_id, "Job")

    # (source, source_external_id) 유니크 제약을 500 대신 409 로
    if payload.source_external_id is not None:
        duplicate = (
            db.query(models.Opportunity)
            .filter(
                models.Opportunity.source == payload.source,
                models.Opportunity.source_external_id
                == payload.source_external_id,
            )
            .first()
        )

        if duplicate is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "opportunity already collected from this source "
                    f"(id={duplicate.id})"
                ),
            )

    fields = payload.model_dump()

    # 직접 넣은 것은 이미 관심이 있다는 뜻이다. 수집기가 가져온
    # discovered 와 다르다. 마감 추적은 interested 부터 시작하므로,
    # 이걸 구분하지 않으면 D-1 짜리를 직접 넣어도 오늘 계획에
    # 안 올라온다.
    if payload.source == "manual" and "status" not in payload.model_fields_set:
        fields["status"] = "interested"

    opportunity = models.Opportunity(**fields)

    db.add(opportunity)
    db.flush()

    # 스킬을 연결하지 않으면 이 기회는 분모만 늘리고 어느 스킬의
    # 분자에도 안 들어간다. 넣을수록 모든 비율이 내려간다.
    opportunity_service.link_skills(db, opportunity)

    db.commit()
    db.refresh(opportunity)

    return opportunity


@router.get("", response_model=list[schemas.OpportunityResponse])
def list_opportunities(
    opportunity_type: str | None = None,
    source: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Opportunity)

    if opportunity_type is not None:
        query = query.filter(
            models.Opportunity.opportunity_type == opportunity_type
        )

    if source is not None:
        query = query.filter(models.Opportunity.source == source)

    if status is not None:
        query = query.filter(models.Opportunity.status == status)

    return query.order_by(models.Opportunity.collected_at.desc()).all()


# --------------------------------
# 수집 / 매칭
#
# 아래 정적 경로들은 반드시 "/{opportunity_id}" 보다 먼저 선언해야 한다.
# 그렇지 않으면 "collect" 가 opportunity_id 로 해석되어 422 가 난다.
# --------------------------------

@router.post("/collect")
def collect_opportunities(db: Session = Depends(get_db)):
    """등록된 수집원을 모두 실행한다.

    실제 외부 연동은 Mission 028 이다. 지금은 mock 만 동작한다.
    """
    return opportunity_service.collect_all(db)


@router.post("/relink-skills")
def relink_skills(db: Session = Depends(get_db)):
    """등록된 모든 기회의 스킬 연결을 다시 만든다.

    link_skills 는 기회를 만들 때만 돈다. 그래서 스킬을 나중에
    추가하면 이미 넣어둔 공고에는 반영되지 않는다 — 본문에
    "강화학습" 이 있어도 그 스킬을 나중에 만들었으면 영원히
    안 걸린다. 수요 계산이 옛 상태로 굳는다.

    사람이 손으로 붙인 연결은 지우지 않는다. 추출기가 찾은 것을
    더할 뿐이다.
    """
    changed = []

    for opportunity in db.query(models.Opportunity).all():
        before = {skill.id for skill in opportunity.skills}

        opportunity_service.link_skills(db, opportunity)

        added = {skill.id for skill in opportunity.skills} - before

        if added:
            changed.append({
                "opportunity_id": opportunity.id,
                "title": opportunity.title,
                "added": sorted(
                    skill.name
                    for skill in opportunity.skills
                    if skill.id in added
                ),
            })

    db.commit()

    return {"changed": changed, "count": len(changed)}


@router.post("/parse")
def parse_posting(
    payload: schemas.PostingParseRequest,
    db: Session = Depends(get_db),
):
    """붙여넣은 공고 글에서 칸을 채운 미리보기. 저장하지 않는다.

    공고 사이트를 앱이 열지 않는다(약관). 사람이 읽은 글만 다룬다.
    """
    return posting_parser.parse_posting(db, payload.text, payload.url)


@router.get("/matches")
def get_opportunity_matches(db: Session = Depends(get_db)):
    """모든 기회를 채점해서 점수 높은 순으로 돌려준다."""
    return {"matches": opportunity_service.score_all(db)}


@router.get("/recommended")
def get_recommended_opportunities(
    limit: int = 3,
    db: Session = Depends(get_db),
):
    """지금 할 만한 것만 추린다.

    목록을 길게 주는 것이 목적이 아니다.
    추천할 게 없으면 빈 목록이 정상이다.
    """
    matches = opportunity_service.recommended(db, limit=limit)

    return {
        "count": len(matches),
        "recommended": matches,
    }


@router.get(
    "/{opportunity_id}",
    response_model=schemas.OpportunityResponse,
)
def get_opportunity(
    opportunity_id: int,
    db: Session = Depends(get_db),
):
    return get_or_404(
        db,
        models.Opportunity,
        opportunity_id,
        "Opportunity",
    )


@router.patch(
    "/{opportunity_id}",
    response_model=schemas.OpportunityResponse,
)
def update_opportunity(
    opportunity_id: int,
    payload: schemas.OpportunityUpdate,
    db: Session = Depends(get_db),
):
    opportunity = get_or_404(
        db,
        models.Opportunity,
        opportunity_id,
        "Opportunity",
    )

    return apply_update(opportunity, payload, db)


@router.delete("/{opportunity_id}")
def delete_opportunity(
    opportunity_id: int,
    db: Session = Depends(get_db),
):
    opportunity = get_or_404(
        db,
        models.Opportunity,
        opportunity_id,
        "Opportunity",
    )

    # 지원서가 달려 있으면 지우지 않는다.
    #
    # 지우면 지원서의 opportunity_id 가 비고, 그 지원서는 어느
    # 기회에도 속하지 않게 된다. 응답 검증이 그런 지원서를 거부해서
    # /applications 전체가 500 이 났다. 화면 하나가 통째로 죽는다.
    #
    # 그리고 내가 지원한 기록은 기회를 정리한다고 사라져도 되는
    # 것이 아니다.
    linked = (
        db.query(models.Application)
        .filter(models.Application.opportunity_id == opportunity_id)
        .count()
    )

    if linked:
        raise HTTPException(
            status_code=409,
            detail=(
                f"지원서 {linked}건이 이 기회에 연결되어 있습니다. "
                "지원서를 먼저 처리하세요 (철회하거나 지우기)."
            ),
        )

    # 지원서가 없더라도 계획에는 올라가 있을 수 있다
    # (add-to-plan 없이 마감 임박으로 들어간 "지원할지 정하기").
    released = today_service.release_plan_tasks(
        db, models.DailyPlanTask.opportunity_id, opportunity_id
    )

    result = delete_instance(opportunity, db)
    result["plan_tasks"] = released

    return result


@router.get("/{opportunity_id}/map")
def get_opportunity_map(
    opportunity_id: int,
    db: Session = Depends(get_db),
):
    """이 공고 기준으로 스킬 → 공부 → 프로젝트 → 경험을 잇는다."""
    opportunity = get_or_404(
        db, models.Opportunity, opportunity_id, "Opportunity"
    )

    return map_service.build_map(db, opportunity)


@router.get("/{opportunity_id}/match")
def get_opportunity_match(
    opportunity_id: int,
    db: Session = Depends(get_db),
):
    """이 기회를 지금 하는 게 가치가 있는지 판단한다."""
    opportunity = get_or_404(
        db,
        models.Opportunity,
        opportunity_id,
        "Opportunity",
    )

    return opportunity_service.score_opportunity(db, opportunity)


@router.get(
    "/{opportunity_id}/skills",
    response_model=list[schemas.SkillResponse],
)
def list_opportunity_skills(
    opportunity_id: int,
    db: Session = Depends(get_db),
):
    opportunity = get_or_404(
        db,
        models.Opportunity,
        opportunity_id,
        "Opportunity",
    )

    return opportunity.skills


@router.post("/{opportunity_id}/skills/{skill_id}")
def link_skill_to_opportunity(
    opportunity_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
):
    opportunity = get_or_404(
        db,
        models.Opportunity,
        opportunity_id,
        "Opportunity",
    )

    skill = get_or_404(db, models.Skill, skill_id, "Skill")

    if skill not in opportunity.skills:
        opportunity.skills.append(skill)
        db.commit()

    return {"message": f"{skill.name} linked to {opportunity.title}"}


@router.delete("/{opportunity_id}/skills/{skill_id}")
def unlink_skill_from_opportunity(
    opportunity_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
):
    opportunity = get_or_404(
        db,
        models.Opportunity,
        opportunity_id,
        "Opportunity",
    )

    skill = get_or_404(db, models.Skill, skill_id, "Skill")

    if skill in opportunity.skills:
        opportunity.skills.remove(skill)
        db.commit()

    return {"message": f"{skill.name} unlinked from {opportunity.title}"}


@router.post("/{opportunity_id}/add-to-plan")
def add_opportunity_to_plan(
    opportunity_id: int,
    # 하한을 두지 않으면 음수 분짜리 태스크가 계획에 들어간다.
    # 상한은 하루가 넘는 블록을 막는다.
    minutes: int = Query(
        opportunity_service.DEFAULT_PLAN_MINUTES, ge=5, le=480
    ),
    db: Session = Depends(get_db),
):
    """이 기회를 오늘 계획에 올린다.

    지원서가 없으면 관심 상태로 하나 만든다.
    기회만 계획에 넣고 지원서를 안 만들면
    나중에 결과를 추적할 곳이 없다.
    """
    opportunity = get_or_404(
        db, models.Opportunity, opportunity_id, "Opportunity"
    )

    return opportunity_service.add_to_plan(db, opportunity, minutes=minutes)
