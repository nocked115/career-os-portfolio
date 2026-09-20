"""Learning Path / Learning Step API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import checklist as checklist_service
from ..services import learning as learning_service
from ..services import step_output as step_output_service
from ..services import today as today_service
from ._common import apply_update, delete_instance, ensure_exists, get_or_404

router = APIRouter(tags=["learning"])


# --------------------------------
# Learning Path
# --------------------------------

def _link_skills(db, path, skill_ids: list[int]) -> None:
    """이 경로가 키우는 스킬들. 대표 스킬(skill_id)은 첫 번째로 맞춘다.

    한 경로가 여러 스킬을 키운다 — 논문 스터디 주차는 PyTorch 와 Computer Vision 을 같이 키운다.
    대표를 남겨 두는 이유는 화면과 회고가 "이 단계는 어느 스킬" 한 줄을 쓰기 때문이다.
    """
    skills = []

    for skill_id in dict.fromkeys(skill_ids):
        skill = db.get(models.Skill, skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
        skills.append(skill)

    path.skills = skills
    path.skill_id = skills[0].id if skills else None


@router.post(
    "/learning-paths",
    response_model=schemas.LearningPathResponse,
    status_code=201,
)
def create_learning_path(
    payload: schemas.LearningPathCreate,
    db: Session = Depends(get_db),
):
    ensure_exists(db, models.Skill, payload.skill_id, "Skill")

    fields = payload.model_dump()
    skill_ids = fields.pop("skill_ids", None)

    path = models.LearningPath(**fields)
    db.add(path)

    if skill_ids is not None:
        _link_skills(db, path, skill_ids)

    db.commit()
    db.refresh(path)

    return path


@router.get(
    "/learning-paths",
    response_model=list[schemas.LearningPathResponse],
)
def list_learning_paths(
    skill_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.LearningPath)

    if skill_id is not None:
        query = query.filter(models.LearningPath.skill_id == skill_id)

    if status is not None:
        query = query.filter(models.LearningPath.status == status)

    return query.all()


@router.get(
    "/learning-paths/{path_id}",
    response_model=schemas.LearningPathResponse,
)
def get_learning_path(
    path_id: int,
    db: Session = Depends(get_db),
):
    return get_or_404(db, models.LearningPath, path_id, "Learning path")


@router.patch(
    "/learning-paths/{path_id}",
    response_model=schemas.LearningPathResponse,
)
def update_learning_path(
    path_id: int,
    payload: schemas.LearningPathUpdate,
    db: Session = Depends(get_db),
):
    path = get_or_404(db, models.LearningPath, path_id, "Learning path")

    ensure_exists(db, models.Skill, payload.skill_id, "Skill")

    changes = payload.model_dump(exclude_unset=True)
    skill_ids = changes.pop("skill_ids", None)

    for field, value in changes.items():
        setattr(path, field, value)

    if skill_ids is not None:
        _link_skills(db, path, skill_ids)

    db.commit()
    db.refresh(path)

    return path


@router.delete("/learning-paths/{path_id}")
def delete_learning_path(
    path_id: int,
    db: Session = Depends(get_db),
):
    path = get_or_404(db, models.LearningPath, path_id, "Learning path")

    # 단계는 경로와 함께 지워진다. 그 단계를 가리키던 오늘 계획 항목과
    # 이 경로를 여는 루틴이 없는 것을 가리키게 두지 않는다.
    released = {"removed": 0, "kept": 0}
    for step in path.steps:
        result = today_service.release_plan_tasks(
            db, models.DailyPlanTask.learning_step_id, step.id
        )
        released["removed"] += result["removed"]
        released["kept"] += result["kept"]

    for routine in db.query(models.Routine).filter(models.Routine.learning_path_id == path.id):
        routine.learning_path_id = None

    result = delete_instance(path, db)
    result["plan_tasks"] = released

    return result


@router.get("/learning-paths/{path_id}/progress")
def get_learning_path_progress(
    path_id: int,
    db: Session = Depends(get_db),
):
    """경로 진행 상황을 조회한다. 읽기 전용.

    진행률 갱신은 스텝이 바뀔 때 일어난다 (services/learning.py).
    """
    path = get_or_404(db, models.LearningPath, path_id, "Learning path")

    summary = learning_service.summarize_steps(path)

    return {
        "learning_path_id": path.id,
        "title": path.title,
        "status": path.status,
        "total_steps": summary["total_steps"],
        "completed_steps": summary["completed_steps"],
        "in_progress_steps": summary["in_progress_steps"],
        "progress_percent": path.progress_percent,
    }


# --------------------------------
# Learning Step
# --------------------------------

def _reject_duplicate_position(db, learning_path_id, position, exclude_id=None):
    """(learning_path_id, position) 유니크 제약을 500 대신 409 로 돌려준다."""
    if position is None:
        return

    query = db.query(models.LearningStep).filter(
        models.LearningStep.learning_path_id == learning_path_id,
        models.LearningStep.position == position,
    )

    if exclude_id is not None:
        query = query.filter(models.LearningStep.id != exclude_id)

    if query.first() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"position {position} is already used in this learning path",
        )


@router.post(
    "/learning-steps",
    response_model=schemas.LearningStepResponse,
    status_code=201,
)
def create_learning_step(
    payload: schemas.LearningStepCreate,
    db: Session = Depends(get_db),
):
    get_or_404(
        db,
        models.LearningPath,
        payload.learning_path_id,
        "Learning path",
    )

    _reject_duplicate_position(
        db,
        payload.learning_path_id,
        payload.position,
    )

    step = models.LearningStep(**payload.model_dump())

    db.add(step)
    db.commit()
    db.refresh(step)

    learning_service.recalculate_path_progress(db, step.learning_path)

    return step


@router.get(
    "/learning-steps",
    response_model=list[schemas.LearningStepResponse],
)
def list_learning_steps(
    learning_path_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.LearningStep)

    if learning_path_id is not None:
        query = query.filter(
            models.LearningStep.learning_path_id == learning_path_id
        )

    if status is not None:
        query = query.filter(models.LearningStep.status == status)

    return query.order_by(models.LearningStep.position).all()


@router.get(
    "/learning-steps/{step_id}",
    response_model=schemas.LearningStepResponse,
)
def get_learning_step(
    step_id: int,
    db: Session = Depends(get_db),
):
    return get_or_404(db, models.LearningStep, step_id, "Learning step")


@router.patch(
    "/learning-steps/{step_id}",
    response_model=schemas.LearningStepResponse,
)
def update_learning_step(
    step_id: int,
    payload: schemas.LearningStepUpdate,
    db: Session = Depends(get_db),
):
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    _reject_duplicate_position(
        db,
        step.learning_path_id,
        payload.position,
        exclude_id=step.id,
    )

    apply_update(step, payload, db)

    learning_service.recalculate_path_progress(db, step.learning_path)

    return step


@router.delete("/learning-steps/{step_id}")
def delete_learning_step(
    step_id: int,
    db: Session = Depends(get_db),
):
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    path = step.learning_path

    # 이 단계를 가리키던 계획 항목도 같이 정리한다.
    released = today_service.release_plan_tasks(
        db, models.DailyPlanTask.learning_step_id, step_id
    )

    result = delete_instance(step, db)
    result["plan_tasks"] = released

    learning_service.recalculate_path_progress(db, path)

    return result


# --------------------------------
# Learning Step <-> Learning Resource
# --------------------------------

# --------------------------------
# 내가 만든 것 — 단계에서 남은 것
# --------------------------------

@router.post("/learning-steps/{step_id}/outputs", status_code=201)
def add_step_output(
    step_id: int,
    body: schemas.StepOutputCreate,
    db: Session = Depends(get_db),
):
    """요약 노트 · 발표 자료 · 코드의 주소를 단계에 붙인다."""
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    output = step_output_service.add(db, step, body.title, body.url)

    return step_output_service.serialize(output)


@router.delete("/step-outputs/{output_id}")
def delete_step_output(
    output_id: int,
    db: Session = Depends(get_db),
):
    output = get_or_404(db, models.LearningStepOutput, output_id, "Step output")

    return delete_instance(output, db)


@router.post("/learning-steps/{step_id}/experience", status_code=201)
def send_step_to_experience(
    step_id: int,
    db: Session = Depends(get_db),
):
    """단계를 경험 초안으로 넘긴다 — 학습이 증거로 남는 자리.

    만든 것이 하나도 없으면 만들지 않는다. 열어 볼 것이 없는 경험은
    지원서에서 쓸 수 없다.
    """
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    existing = step_output_service.experience_of(db, step)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"이 단계는 이미 경험 '{existing.title}' 으로 보냈어요.",
        )

    if not step.outputs:
        raise HTTPException(
            status_code=400,
            detail="먼저 이 단계에서 만든 것(노트 · 자료 · 코드)의 주소를 하나 이상 넣어 주세요.",
        )

    experience = step_output_service.to_experience(db, step)

    return {
        "id": experience.id,
        "title": experience.title,
        "message": (
            "경험으로 보냈어요. 상황 · 역할 · 수치는 경험 화면에서 채우면 됩니다."
        ),
    }


@router.post("/learning-steps/{step_id}/resources/{resource_id}")
def link_resource_to_step(
    step_id: int,
    resource_id: int,
    db: Session = Depends(get_db),
):
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    resource = get_or_404(
        db,
        models.LearningResource,
        resource_id,
        "Learning resource",
    )

    if resource not in step.resources:
        step.resources.append(resource)
        db.commit()

    return {"message": f"{resource.title} linked to {step.title}"}


@router.delete("/learning-steps/{step_id}/resources/{resource_id}")
def unlink_resource_from_step(
    step_id: int,
    resource_id: int,
    db: Session = Depends(get_db),
):
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    resource = get_or_404(
        db,
        models.LearningResource,
        resource_id,
        "Learning resource",
    )

    if resource in step.resources:
        step.resources.remove(resource)
        db.commit()

    return {"message": f"{resource.title} unlinked from {step.title}"}


@router.get(
    "/learning-steps/{step_id}/resources",
    response_model=list[schemas.LearningResourceResponse],
)
def list_step_resources(
    step_id: int,
    db: Session = Depends(get_db),
):
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    return step.resources


# --------------------------------
# Learning Session (Mission 022)
# --------------------------------

@router.get("/learning-steps/{step_id}/session")
def get_learning_session(
    step_id: int,
    db: Session = Depends(get_db),
):
    """집중 학습 화면에 필요한 것을 한 번에 돌려준다.

    WHY NOW 설명은 저장된 공고/프로젝트/학습 기록에서만 만든다.
    """
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    return learning_service.build_session(db, step)


@router.post("/learning-steps/{step_id}/start")
def start_learning_step(
    step_id: int,
    db: Session = Depends(get_db),
):
    """스텝을 진행 중으로 표시한다."""
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    if step.status == "not_started":
        step.status = "in_progress"
        db.commit()
        db.refresh(step)

        learning_service.recalculate_path_progress(db, step.learning_path)

    return learning_service.build_session(db, step)


@router.post("/learning-steps/{step_id}/complete")
def complete_learning_step(
    step_id: int,
    db: Session = Depends(get_db),
):
    """스텝을 완료 처리하고 경로 진행률까지 갱신한다.

    이 한 번의 호출로 학습 -> 진행률 -> 우선순위 -> Today Plan 이 이어진다.

    화면이 "무엇이 바뀌었는지" 를 말할 수 있게 전과 후를 함께 돌려준다.
    전에는 끝낸 뒤 "반영되었습니다" 한 줄뿐이라 무엇이 얼마나 바뀌었는지
    알 수 없었다.
    """
    step = get_or_404(db, models.LearningStep, step_id, "Learning step")

    path = step.learning_path
    before = learning_service.summarize_steps(path)
    already = step.status == "completed"

    step.status = "completed"
    step.progress_percent = 100
    if not (already and step.completed_at):
        step.completed_at = datetime.now()

    # 오늘 계획에 같은 단계가 있으면 함께 끝낸다. 세션에서 끝냈는데
    # Today 에는 아직 할 일로 남아 있으면 두 화면이 다른 말을 한다.
    today_tasks = (
        db.query(models.DailyPlanTask)
        .filter(
            models.DailyPlanTask.plan_date == datetime.now().date(),
            models.DailyPlanTask.learning_step_id == step.id,
            models.DailyPlanTask.status == "planned",
        )
        .all()
    )

    for task in today_tasks:
        task.status = "done"
        task.completed_at = datetime.now()

    db.commit()
    db.refresh(step)

    summary = learning_service.recalculate_path_progress(db, path)

    effects = []

    if not already:
        effects.append(
            f"학습 진행률 {before['progress_percent']}% → "
            f"{summary['progress_percent']}%"
        )

        if path.skill is not None:
            effects.append(
                f"{path.skill.name} 의 학습 진행이 우선순위 계산에 반영됩니다"
            )

    for task in today_tasks:
        effects.append(f"오늘 계획의 '{task.title}' 도 완료로 표시했습니다")

    # 완료는 사람이 정한다. 다만 체크 안 한 항목이 남았다는 사실은 숨기지 않는다.
    unchecked = checklist_service.remaining(step)
    if unchecked:
        effects.append(f"체크 안 한 항목 {unchecked}개가 남아 있어요 — 단계는 완료로 두었습니다")

    next_step = next(
        (
            item
            for item in sorted(path.steps, key=lambda item: item.position)
            if item.status != "completed"
        ),
        None,
    )

    return {
        "step_id": step.id,
        "status": step.status,
        "completed_at": step.completed_at,
        "already_completed": already,
        "effects": effects,
        "next_step": (
            {"id": next_step.id, "title": next_step.title} if next_step else None
        ),
        "learning_path": {
            "id": path.id,
            "title": path.title,
            "status": path.status,
            "progress_before": before["progress_percent"],
            "progress_percent": path.progress_percent,
            "completed_steps": summary["completed_steps"],
            "total_steps": summary["total_steps"],
        },
    }


# --------------------------------
# Learning Resource 수정 / 삭제
#
# 생성과 목록 조회는 기존대로 main.py 의 /resources 에 있다.
# Mission 022 에서 중요도를 다루려면 부분 수정이 필요해서 여기에 추가했다.
# --------------------------------

@router.patch(
    "/resources/{resource_id}",
    response_model=schemas.LearningResourceResponse,
)
def update_resource(
    resource_id: int,
    payload: schemas.LearningResourceUpdate,
    db: Session = Depends(get_db),
):
    resource = get_or_404(
        db,
        models.LearningResource,
        resource_id,
        "Learning resource",
    )

    return apply_update(resource, payload, db)


@router.delete("/resources/{resource_id}")
def delete_resource(
    resource_id: int,
    db: Session = Depends(get_db),
):
    resource = get_or_404(
        db,
        models.LearningResource,
        resource_id,
        "Learning resource",
    )

    released = today_service.release_plan_tasks(
        db, models.DailyPlanTask.learning_resource_id, resource_id
    )

    result = delete_instance(resource, db)
    result["plan_tasks"] = released

    return result
