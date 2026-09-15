"""학습 진행 관련 계산 - 단일 출처.

Mission 021 에서는 진행률 갱신이 `GET /learning-paths/{id}/progress`
안에 들어있었다. 조회 요청이 상태를 바꾸는 구조라
스텝을 고쳐도 그 엔드포인트를 부르기 전까지는 경로 진행률이 낡은 값이었다.

Mission 022 부터는 스텝이 바뀔 때마다 여기서 다시 계산하고,
조회 엔드포인트는 읽기만 한다.
"""

from .. import models
from . import checklist as checklist_service


COMPLETED = "completed"
IN_PROGRESS = "in_progress"
NOT_STARTED = "not_started"


def summarize_steps(path) -> dict:
    """경로의 스텝 상태를 집계한다. 저장하지 않는다."""
    steps = path.steps
    total = len(steps)

    completed = sum(1 for step in steps if step.status == COMPLETED)

    in_progress = sum(1 for step in steps if step.status == IN_PROGRESS)

    progress_percent = round(completed / total * 100) if total else 0

    if total and completed == total:
        status = COMPLETED
    elif completed or in_progress:
        status = IN_PROGRESS
    else:
        status = NOT_STARTED

    return {
        "total_steps": total,
        "completed_steps": completed,
        "in_progress_steps": in_progress,
        "progress_percent": progress_percent,
        "status": status,
    }


def recalculate_path_progress(db, path, commit: bool = True):
    """스텝 상태에서 경로 진행률과 상태를 다시 계산해 저장한다.

    스텝이 생기거나 바뀌거나 지워질 때마다 호출한다.
    """
    summary = summarize_steps(path)

    path.progress_percent = summary["progress_percent"]

    # 아직 아무 스텝도 손대지 않았다면 경로 상태를 강제로 되돌리지 않는다.
    # 사용자가 직접 status 를 바꿔둔 경우를 존중한다.
    if summary["total_steps"] > 0:
        path.status = summary["status"]

    if commit:
        db.commit()
        db.refresh(path)

    return summary


# --------------------------------
# Learning Session (Mission 022)
# --------------------------------

IMPORTANCE_ORDER = ["primary", "supplementary", "deep_dive"]


def parse_goals(step) -> list[str]:
    """스텝 설명의 각 줄을 오늘의 목표로 본다.

    별도의 목표 테이블을 만들지 않았다.
    설명에 적힌 것 외에는 아무것도 지어내지 않는다.
    """
    if not step.description:
        return []

    return [
        line.strip().lstrip("-*").strip()
        for line in step.description.splitlines()
        if line.strip()
    ]


def group_materials(step) -> dict:
    """스텝의 자료를 중요도별로 묶는다.

    지금 필요한 것(primary)을 먼저 보여주고
    나머지는 뒤로 미루기 위한 것이다.
    """
    grouped = {key: [] for key in IMPORTANCE_ORDER}

    for resource in step.resources:
        key = resource.importance if resource.importance in grouped else "primary"

        grouped[key].append({
            "id": resource.id,
            "title": resource.title,
            "url": resource.url,
            "resource_type": resource.resource_type,
            "duration_minutes": resource.duration_minutes,
            "importance": resource.importance,
            "status": resource.status,
        })

    return grouped


def build_why_now(db, skill):
    """왜 지금 이걸 배워야 하는지 - 실제 데이터로만 구성한다.

    임의의 문장이나 추정치를 만들어내지 않는다.
    모든 숫자는 저장된 공고/프로젝트/학습 기록에서 나온다.
    """
    # 순환 임포트를 피하려고 지역에서 가져온다.
    from . import priority as priority_service

    if skill is None:
        return None

    entries = priority_service.build_skill_priorities(db)

    rank = None
    entry = None

    for index, item in enumerate(entries, start=1):
        if item["skill"].id == skill.id:
            rank = index
            entry = item
            break

    if entry is None:
        return None

    # 모수는 Opportunity 하나다 (priority.build_skill_priorities 와 같은 기준).
    total_demand = db.query(models.Opportunity).count()
    demand_requiring = len(skill.opportunities)

    reasons = []

    if total_demand and demand_requiring:
        reasons.append(
            f"모아둔 기회 {total_demand}건 중 {demand_requiring}건이 "
            f"{skill.name} 을(를) 요구합니다."
        )
    elif not total_demand:
        reasons.append(
            "아직 모아둔 기회가 없어 수요를 계산할 수 없습니다."
        )
    else:
        reasons.append(
            f"모아둔 기회 중 {skill.name} 을(를) 요구하는 것은 없습니다."
        )

    reasons.append(f"현재 레벨은 {entry['my_level']} 입니다.")

    if entry["has_project_evidence"]:
        names = ", ".join(
            project.name for project in entry["career_projects"]
        )
        reasons.append(f"관련 프로젝트 증거가 있습니다: {names}.")
    else:
        reasons.append("관련 프로젝트 증거가 아직 없습니다.")

    if entry["has_learning_evidence"]:
        reasons.append(
            f"학습 경로 진행률은 {entry['learning_progress']}% 입니다."
        )

    return {
        "skill": skill.name,
        "priority_rank": rank,
        "priority_score": entry["priority_score"],
        "market_percentage": entry["market_percentage"],
        "demand_requiring": demand_requiring,
        "total_demand": total_demand,
        "my_level": entry["my_level"],
        "has_project_evidence": entry["has_project_evidence"],
        "learning_progress": entry["learning_progress"],
        "reasons": reasons,
    }


def build_session(db, step) -> dict:
    """Learning Session 화면에 필요한 것을 한 번에 모아준다."""
    path = step.learning_path
    skill = path.skill if path else None

    materials = group_materials(step)

    material_minutes = sum(
        item["duration_minutes"]
        for group in materials.values()
        for item in group
    )

    # Phase 2: 내 라이브러리에서 오늘 볼 것만 고른다.
    # 단계의 예상 시간을 예산으로 쓴다.
    from . import library as library_service

    selection = library_service.select_for_step(
        db, step, step.estimated_minutes or 45
    )

    return {
        "step": {
            "id": step.id,
            "title": step.title,
            "description": step.description,
            "position": step.position,
            "status": step.status,
            "progress_percent": step.progress_percent,
            "estimated_minutes": step.estimated_minutes,
            "completed_at": step.completed_at,
            "due_date": step.due_date,
        },
        "learning_path": {
            "id": path.id,
            "title": path.title,
            "status": path.status,
            "progress_percent": path.progress_percent,
        } if path else None,
        "skill": {
            "id": skill.id,
            "name": skill.name,
            "level": skill.level,
        } if skill else None,
        "why_now": build_why_now(db, skill),
        "goals": parse_goals(step),
        # 서버에 남는 체크리스트. 위의 goals 는 단계 설명의 줄이라 체크가
        # 브라우저에만 남았다 — 화면은 체크리스트가 있으면 이쪽을 쓴다.
        "checklist": checklist_service.build_checklist(step),
        "materials": materials,
        "material_minutes": material_minutes,

        # 오늘 볼 것과 치운 것.
        # 치운 것을 숨기면 선별했다는 증거가 사라진다.
        "selection": selection,
    }


def find_next_step(skill):
    """이 스킬에서 다음에 할 학습 스텝을 고른다.

    진행 중인 스텝이 있으면 그것을, 없으면 아직 시작 안 한 것 중
    가장 앞 순서를 고른다. 완료된 스텝은 건너뛴다.
    """
    if skill is None:
        return None

    candidates = [
        step
        for path in skill.learning_paths
        for step in path.steps
        if step.status != COMPLETED
    ]

    if not candidates:
        return None

    # 진행 중인 것을 먼저, 그다음 순서대로
    candidates.sort(
        key=lambda step: (step.status != IN_PROGRESS, step.position)
    )

    return candidates[0]


def summarize_step_for_plan(step) -> dict:
    """Today / Weekly Plan 에 끼워 넣을 최소 정보."""
    if step is None:
        return None

    path = step.learning_path

    return {
        "step_id": step.id,
        "title": step.title,
        "status": step.status,
        "estimated_minutes": step.estimated_minutes,
        "learning_path_id": path.id if path else None,
        "learning_path_title": path.title if path else None,
        "session_url": f"/learning-steps/{step.id}/session",
    }
