"""학습 진행 관련 계산 - 단일 출처.

Mission 021 에서는 진행률 갱신이 `GET /learning-paths/{id}/progress`
안에 들어있었다. 조회 요청이 상태를 바꾸는 구조라
스텝을 고쳐도 그 엔드포인트를 부르기 전까지는 경로 진행률이 낡은 값이었다.

Mission 022 부터는 스텝이 바뀔 때마다 여기서 다시 계산하고,
조회 엔드포인트는 읽기만 한다.
"""

from .. import models
from . import checklist as checklist_service
from . import market as market_service
from . import step_output as step_output_service


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
    total_demand = market_service.count_opportunities(db)
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
        # 오늘 몫 — 화면이 이 범위에만 테두리를 친다. 오늘 계획이 이
        # 단계에 준 시간을 그대로 쓴다. 계획에 없으면 자르지 않는다 —
        # 오늘 하기로 한 일이 아닌데 "오늘은 여기까지" 라고 말할 수 없다.
        "today_slice": checklist_service.today_slice(step, _planned_minutes(db, step)),
        "materials": materials,
        "material_minutes": material_minutes,

        # 이 단계가 덮는 자료의 장. 끝내면 같이 끝난다.
        # 붙은 것과, 붙일 수 있는 것(연결된 자료의 나머지 장)을 함께 준다 —
        # 화면에서 바로 고를 수 있어야 "어느 장이었더라" 로 되돌아가지 않는다.
        "segments": _step_segments(db, step),

        # 오늘 볼 것과 치운 것.
        # 치운 것을 숨기면 선별했다는 증거가 사라진다.
        "selection": selection,

        # 이 단계에서 내가 만든 것과, 이미 경험으로 넘겼는지.
        **step_output_service.session_summary(db, step),
    }


def _planned_minutes(db, step) -> int | None:
    """오늘 계획이 이 단계에 준 시간. 계획에 없으면 None."""
    from datetime import date as _date

    from .. import models as _models

    task = (
        db.query(_models.DailyPlanTask)
        .filter(
            _models.DailyPlanTask.plan_date == _date.today(),
            _models.DailyPlanTask.learning_step_id == step.id,
            _models.DailyPlanTask.status.in_(("planned", "done")),
        )
        .first()
    )

    return task.minutes if task is not None else None


def _step_segments(db, step) -> dict:
    """이 단계가 덮는 장과, 붙일 수 있는 장.

    붙일 후보는 **이미 이 단계에 연결된 자료**의 장 중 아직 어느 단계에도
    안 붙은 것이다. 라이브러리 전체를 내밀면 고를 수가 없다.
    """
    def row(segment):
        return {
            "id": segment.id,
            "label": segment.label,
            "minutes": segment.estimated_minutes,
            "status": segment.status,
            "note": segment.note or "",
            "resource_id": segment.learning_resource_id,
            "resource_title": segment.resource.title if segment.resource else "",
        }

    attached = sorted(
        step.segments,
        key=lambda item: (item.learning_resource_id, item.position),
    )

    # 고를 후보는 두 군데서 온다.
    #
    #   1. 이미 이 단계에 연결된 자료
    #   2. **이 경로의 스킬로 등록된 자료** — 아직 단계에 안 걸린 것도
    #
    # 2가 없으면 "자료를 단계에 연결" 하고 "장을 고르기" 를 따로 해야 한다.
    # 장을 붙이면 그 자료도 같이 걸리므로(attach_segment_to_step) 한 번으로
    # 끝낼 수 있다. 라이브러리 전체가 아니라 **이 경로의 스킬** 로 묶인
    # 것만 본다 — 42개를 다 내밀면 고를 수가 없다.
    path = step.learning_path
    skill_ids = {skill.id for skill in (path.skills if path else [])}

    if path is not None and path.skill_id is not None:
        skill_ids.add(path.skill_id)

    pool = {resource.id: resource for resource in step.resources}

    for resource in db.query(models.LearningResource).filter(
        models.LearningResource.skill_id.in_(skill_ids or {-1})
    ):
        pool.setdefault(resource.id, resource)

    available = sorted(
        (
            segment
            for resource in pool.values()
            for segment in resource.segments
            if segment.learning_step_id is None
        ),
        key=lambda item: (item.learning_resource_id, item.position),
    )

    return {
        "attached": [row(segment) for segment in attached],
        "available": [row(segment) for segment in available],
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
        for path in skill.growing_paths
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


# --------------------------------
# 끝낸 뒤 — 영수증
# --------------------------------

def completion_receipt(db, step) -> dict:
    """한 단계를 끝냈을 때 내주는 영수증.

    수현: "완료 표시를 했는데 그냥 '완료했습니다' 하고 끝. 참 잘했어요
    도장이라도 찍어주던지, 결과표를 내주던지 영수증처럼 — 총 걸린 시간
    3시간 (예상보다 00시간 오버) / 남긴 자료들 노션 등."

    맞는 말이다. 끝낸 순간이 **가장 많은 것이 모여 있는 때**인데 앱은
    그걸 그냥 흘려보냈다. 여기서 안 보여주면, 나중에 경험으로 꺼낼 때
    "내가 뭘 했더라" 를 처음부터 더듬어야 한다.

    **지어내지 않는다.** 시간을 안 적었으면 안 적었다고 하고, 남긴 것이
    없으면 없다고 한다. 없는 성과를 채워 넣으면 영수증이 아니라 상장이 된다.
    """
    from .. import models

    tasks = (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.learning_step_id == step.id)
        .all()
    )

    # 실제로 적은 시간만 센다. 안 적은 날은 세지 않는다 — 0 분으로 치면
    # "한 번에 끝냈다" 는 거짓말이 된다.
    measured = [task for task in tasks if task.actual_minutes is not None]
    actual = sum(task.actual_minutes for task in measured)

    estimated = step.estimated_minutes or 0
    gap = (actual - estimated) if (measured and estimated) else None

    items = sorted(step.checklist, key=lambda item: (item.position, item.id))
    done_items = [item for item in items if item.done]

    # 며칠에 걸쳐 했나. 하루에 끝낸 것과 2주를 끈 것은 다른 이야기다.
    days = sorted({task.plan_date for task in tasks if task.plan_date})

    path = step.learning_path

    return {
        "step": {"id": step.id, "title": step.title},
        "path": {"id": path.id, "title": path.title} if path else None,

        "estimated_minutes": estimated,
        # 적은 기록이 없으면 None. 0 이 아니다.
        "actual_minutes": actual if measured else None,
        "measured_days": len(measured),
        "gap_minutes": gap,

        "checked": len(done_items),
        "total_items": len(items),

        "span_days": (days[-1] - days[0]).days + 1 if days else None,
        "first_day": days[0].isoformat() if days else None,
        "last_day": days[-1].isoformat() if days else None,

        # 남긴 것 — 노션 · 깃허브 · 드라이브 주소.
        "outputs": [
            {"id": output.id, "title": output.title, "url": output.url}
            for output in step.outputs
        ],

        # 이 단계가 키우는 스킬. 무엇을 증명했는지가 영수증의 본문이다.
        "skills": sorted({
            skill.name
            for skill in ((path.skills if path else []) or [])
        }) or ([path.skill.name] if path and path.skill else []),

        # 다음 단계. 끝낸 자리에서 다음이 보여야 멈추지 않는다.
        "next_step": _next_after(step),

        # 비어 있는 것. 채우라고 말하되 채워 넣지는 않는다.
        "missing": [
            label for label, empty in (
                ("걸린 시간", not measured),
                ("남긴 자료", not step.outputs),
            ) if empty
        ],
    }


def _next_after(step):
    path = step.learning_path

    if path is None:
        return None

    later = sorted(
        (
            other for other in path.steps
            if other.position > step.position and other.status != COMPLETED
        ),
        key=lambda item: item.position,
    )

    if not later:
        return None

    return {"id": later[0].id, "title": later[0].title,
            "minutes": later[0].estimated_minutes or 0}
