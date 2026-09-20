"""학습 우선순위 계산 - 단일 출처.

Mission 021 이전에는 이 계산이 네 곳(`/analytics/learning-priority`,
`/today`, `/weekly-plan`, `agents/tools.py`)에 복사되어 있었고
서로 결과가 달랐다.

  - agents/tools.py 는 evidence_weight 를 빼먹어서 Agent 와 API 가
    서로 다른 점수를 보고했다.
  - /analytics/learning-priority 는 max(0, ...) 가드가 없어서
    level 이 MAX_SKILL_LEVEL 을 넘으면 음수 점수가 나왔다.

이제 모든 호출부가 이 모듈을 쓴다.
"""

from .. import models
from . import market as market_service


# 스킬 숙련도 상한. skill_gap 은 이 값과 현재 레벨의 차이다.
MAX_SKILL_LEVEL = 4

# 증거의 세기 (0.0 ~ 0.85).
#
# 전에는 "커리어 프로젝트가 하나라도 있으면 0.5" 였다. 진행률도
# 결과물도 보지 않았기 때문에, 0% 짜리 빈 프로젝트를 만들기만 해도
# 그 스킬의 우선순위가 반토막 났다.
#
# 프로젝트가 있다는 사실과 그것이 증거라는 사실은 다르다.
# 어디까지 갔는지에 따라 세기를 나눈다.
PROJECT_EVIDENCE = {
    "started": 0.10,     # 만들기로 했다
    "in_progress": 0.25,  # 만드는 중이다
    "completed": 0.50,    # 만들었다
    "shown": 0.70,        # 보여줄 수 있다 (GitHub · 데모 · 결과)
    "used": 0.85,         # 경험으로 남았다
}

# 학습으로 낼 수 있는 최대 세기 (Mission 022).
#
# 학습은 프로젝트보다 약한 증거다. 프로젝트는 "만들어봤다" 이고
# 학습은 "배웠다" 이기 때문이다. 경로를 100% 끝내도 완료한
# 프로젝트 하나(0.50)를 넘지 못한다.
MAX_LEARNING_EVIDENCE = 0.4

# 증거가 아무리 강해도 우선순위를 0 으로 만들지는 않는다.
# 다 아는 것처럼 보여도 시장은 계속 움직인다.
EVIDENCE_WEIGHT_FLOOR = 0.15

# 목표 직무와 관련 없는 스킬의 가중치 (Phase 1).
#
# 목표 직무를 정해두면 "무엇이 중요한가" 의 기준이 전체 공고에서
# 내 목표로 바뀐다. 목표와 무관한 스킬은 시장 수요가 높아도
# 지금 내가 먼저 할 일은 아니다.
#
# 0 으로 만들지는 않는다. 목표와 무관해 보여도 수요가 아주 높으면
# 알아볼 가치는 있고, 목표는 바뀔 수 있기 때문이다.
#
# 활성 목표 직무가 없으면 모든 스킬이 1.0 이라 이전과 결과가 같다.
TARGET_OFF_WEIGHT = 0.6
TARGET_ON_WEIGHT = 1.0


def calculate_market_percentage(demand_count: int, total_demand: int) -> int:
    """수집한 기회 중 이 스킬을 요구하는 비율.

    "시장 수요" 라고 부르지만 실제로 재는 것은 **내가 모아둔 기회** 다.
    채용 시장 전체를 보지 않는다. 화면도 그렇게 쓴다.
    """
    if total_demand <= 0:
        return 0

    return round(demand_count / total_demand * 100)


def calculate_skill_gap(level: int) -> int:
    """상한까지 남은 격차. 음수가 되지 않도록 0 에서 자른다."""
    return max(0, MAX_SKILL_LEVEL - level)


def calculate_learning_progress(skill) -> int:
    """이 스킬에 연결된 학습 경로들의 평균 진행률 (0~100).

    경로가 없으면 0. 즉 학습 증거가 없는 상태다.
    """
    paths = skill.growing_paths

    if not paths:
        return 0

    total = sum(path.progress_percent or 0 for path in paths)

    return round(total / len(paths))


def _has_experience(db, project) -> bool:
    """이 프로젝트가 Experience 로 옮겨졌는지.

    옮겨졌다는 건 이력서에 쓸 수 있는 형태가 됐다는 뜻이다.
    """
    return (
        db.query(models.Experience)
        .filter(models.Experience.project_id == project.id)
        .first()
        is not None
    )


def project_evidence_strength(project, has_experience: bool = False) -> float:
    """이 프로젝트 하나가 내는 증거의 세기.

    있다/없다가 아니라 어디까지 갔는지를 본다.
    """
    if not project.career_related:
        return 0.0

    progress = project.progress_percent or 0
    done = project.status == "completed" or progress >= 100

    if not done:
        return (
            PROJECT_EVIDENCE["in_progress"]
            if progress > 0
            else PROJECT_EVIDENCE["started"]
        )

    can_show = bool(
        project.github_url or project.demo_url or project.results
    )

    # 최고 등급은 보여줄 것이 있고 경험으로 정리까지 된 경우다.
    # Experience 로 옮기는 것은 클릭 한 번이라, 그것만으로는
    # GitHub 저장소 하나보다 더 증명하지 못한다.
    if has_experience and can_show:
        return PROJECT_EVIDENCE["used"]

    if has_experience or can_show:
        return PROJECT_EVIDENCE["shown"]

    # 끝났는데 보여줄 것이 없으면 아직 완전한 증거가 아니다.
    return PROJECT_EVIDENCE["completed"]


def combine_evidence(project_strength: float, learning_strength: float) -> float:
    """서로 다른 두 증거를 합친다.

    더하면 1.0 을 넘고, 큰 쪽만 쓰면 둘 다 있는 경우가 하나만 있는
    경우와 같아진다. 겹치는 만큼을 빼서 합친다.
    """
    combined = (
        project_strength
        + learning_strength
        - project_strength * learning_strength
    )

    return min(combined, PROJECT_EVIDENCE["used"])


def calculate_learning_weight(learning_progress: int) -> float:
    """학습 진행도를 증거 가중치로 바꾼다.

    진행률 0 이면 1.0 (감소 없음), 100 이면 1.0 - MAX_LEARNING_EVIDENCE_DISCOUNT.
    """
    ratio = min(max(learning_progress, 0), 100) / 100

    return round(1.0 - MAX_LEARNING_EVIDENCE * ratio, 4)


def get_active_target_career(db):
    """활성 목표 직무. 없으면 None."""
    return (
        db.query(models.TargetCareer)
        .filter(models.TargetCareer.is_active.is_(True))
        .first()
    )


def calculate_target_weight(skill, target_skill_ids):
    """목표 직무 관련성 가중치.

    목표가 없으면(빈 집합) 모든 스킬이 1.0 이다.
    """
    if not target_skill_ids:
        return TARGET_ON_WEIGHT

    return (
        TARGET_ON_WEIGHT
        if skill.id in target_skill_ids
        else TARGET_OFF_WEIGHT
    )


def calculate_priority_score(
    market_percentage: int,
    skill_gap: int,
    evidence_weight: float,
) -> int:
    """시장 수요 x 스킬 격차 x 증거 가중치."""
    return round(market_percentage * skill_gap * evidence_weight)


def build_skill_priorities(db):
    """모든 스킬의 우선순위를 계산해 높은 순으로 돌려준다.

    각 항목은 ORM 객체(`skill`, `career_projects`)와 계산 결과를 함께 담는다.
    API 응답으로 내보낼 때는 `serialize_priority()` 를 쓴다.
    """
    skills = db.query(models.Skill).all()

    # 모수는 Opportunity 하나다.
    #
    # 전에는 Job 을 셌는데, Opportunity -> Job 브리지가 job 타입만
    # 넘겨서 공모전·대외활동이 빠졌다. 그래서 같은 "수요" 를 두
    # 테이블이 다르게 셌다 — AWS 가 한쪽에서는 1/1, 다른 쪽에서는 0/3.
    #
    # Job 으로 들어온 것도 이제 Opportunity 에 남는다
    # (opportunity.bridge_from_legacy_job).
    total_demand = market_service.count_opportunities(db)

    target_career = get_active_target_career(db)
    target_skill_ids = (
        {skill.id for skill in target_career.skills}
        if target_career
        else set()
    )

    entries = []

    for skill in skills:
        demand_count = len(skill.opportunities)

        market_percentage = calculate_market_percentage(
            demand_count=demand_count,
            total_demand=total_demand,
        )

        skill_gap = calculate_skill_gap(skill.level or 0)

        career_projects = [
            project
            for project in skill.projects
            if project.career_related
        ]

        has_project_evidence = len(career_projects) > 0

        # 프로젝트가 있다는 사실과 그것이 증거라는 사실은 다르다.
        # 가장 멀리 간 프로젝트 하나의 세기를 쓴다.
        project_strength = max(
            (
                project_evidence_strength(
                    project,
                    has_experience=_has_experience(db, project),
                )
                for project in career_projects
            ),
            default=0.0,
        )

        # Mission 022: 학습 진행도도 증거로 친다.
        learning_progress = calculate_learning_progress(skill)
        learning_strength = round(
            MAX_LEARNING_EVIDENCE * min(max(learning_progress, 0), 100) / 100,
            4,
        )

        evidence_strength = combine_evidence(
            project_strength, learning_strength
        )

        evidence_weight = max(
            EVIDENCE_WEIGHT_FLOOR, round(1.0 - evidence_strength, 4)
        )

        # 화면과 기존 테스트가 쓰는 이름은 유지한다.
        project_weight = round(1.0 - project_strength, 4)
        learning_weight = calculate_learning_weight(learning_progress)

        # Phase 1: 목표 직무 관련성.
        target_weight = calculate_target_weight(skill, target_skill_ids)

        entries.append({
            "skill": skill,
            "skill_name": skill.name,
            "market_percentage": market_percentage,
            # 분모 없는 퍼센트는 근거가 아니다.
            # 화면은 "100%" 가 아니라 "1건 중 1건" 으로 쓴다.
            "demand_count": demand_count,
            "total_demand": total_demand,
            "my_level": skill.level or 0,
            "skill_gap": skill_gap,
            "career_projects": career_projects,
            "has_project_evidence": has_project_evidence,
            "learning_paths": list(skill.growing_paths),
            "learning_progress": learning_progress,
            "has_learning_evidence": learning_progress > 0,
            "project_weight": project_weight,
            "learning_weight": learning_weight,
            "project_strength": project_strength,
            "learning_strength": learning_strength,
            "evidence_strength": round(evidence_strength, 4),
            "evidence_weight": evidence_weight,
            "target_career": target_career.title if target_career else None,
            "target_relevant": (
                None if not target_skill_ids else skill.id in target_skill_ids
            ),
            "target_weight": target_weight,
            "priority_score": calculate_priority_score(
                market_percentage=market_percentage,
                skill_gap=skill_gap,
                evidence_weight=round(evidence_weight * target_weight, 4),
            ),
        })

    entries.sort(
        key=lambda entry: entry["priority_score"],
        reverse=True,
    )

    return entries


def serialize_resource(resource) -> dict:
    return {
        "id": resource.id,
        "title": resource.title,
        "url": resource.url,
        "resource_type": resource.resource_type,
        "duration_minutes": resource.duration_minutes,
        "status": resource.status,
    }


def serialize_priority(entry, include_resources: bool = False) -> dict:
    """ORM 객체를 걷어내고 JSON 으로 내보낼 수 있는 형태로 바꾼다."""
    result = {
        # 화면이 레벨을 고치려면 무엇을 고칠지 알아야 한다.
        # 이름만 주면 PATCH 할 대상을 찾을 수 없다.
        "skill_id": entry["skill"].id,
        "skill": entry["skill_name"],
        "market_percentage": entry["market_percentage"],
        "demand_count": entry["demand_count"],
        "total_demand": entry["total_demand"],
        "my_level": entry["my_level"],
        "skill_gap": entry["skill_gap"],
        "career_projects": [
            project.name
            for project in entry["career_projects"]
        ],
        "has_project_evidence": entry["has_project_evidence"],
        "learning_progress": entry["learning_progress"],
        "has_learning_evidence": entry["has_learning_evidence"],
        "project_weight": entry["project_weight"],
        "learning_weight": entry["learning_weight"],
        # 증거가 얼마나 센지. 화면이 "왜 이 점수인가" 를 설명하려면
        # 가중치만으로는 부족하고 세기가 있어야 한다.
        "project_strength": entry["project_strength"],
        "learning_strength": entry["learning_strength"],
        "evidence_strength": entry["evidence_strength"],
        "target_career": entry["target_career"],
        "target_relevant": entry["target_relevant"],
        "target_weight": entry["target_weight"],
        "evidence_weight": entry["evidence_weight"],
        "priority_score": entry["priority_score"],
    }

    if include_resources:
        result["resources"] = [
            serialize_resource(resource)
            for resource in entry["skill"].resources
        ]

    return result


def get_learning_priority(db, include_resources: bool = False) -> list[dict]:
    """직렬화까지 끝난 우선순위 목록."""
    return [
        serialize_priority(entry, include_resources=include_resources)
        for entry in build_skill_priorities(db)
    ]
