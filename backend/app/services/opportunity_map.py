"""공고 하나를 기준으로 펼친 지도.

Opportunities · Learning · Projects · Experience · Applications 가 각자
따로 떨어져 있어서, "이 공고 때문에 이 챕터를 읽고 있고, 그게 이
프로젝트가 되고, 그 경험이 이 지원서에 들어간다" 는 흐름을 머릿속으로
이어야 했다.

칸은 전부 이미 있었다. 여기서는 새로 계산하지 않고 선만 잇는다.

    공고 → 요구 스킬 → 레벨 → 공부(챕터) → 프로젝트 → 경험

각 스킬이 어디까지 차 있는지는 **셀 수 있는 것으로만** 정한다.
경험이 연결돼 있으면 "쓸 수 있음", 프로젝트만 있으면 "만드는 중",
끝낸 챕터나 레벨이 있으면 "공부 중", 아무것도 없으면 "비어 있음".
"""

from .. import models
from . import priority as priority_service
from . import today as today_service


# 칸이 얼마나 찼는가. 뒤로 갈수록 자소서에 쓸 수 있는 것에 가깝다.
STAGE_EMPTY = "empty"
STAGE_STUDYING = "studying"
STAGE_BUILDING = "building"
STAGE_COVERED = "covered"

STAGE_LABELS = {
    STAGE_EMPTY: "비어 있음",
    STAGE_STUDYING: "공부 중",
    STAGE_BUILDING: "만드는 중",
    STAGE_COVERED: "쓸 수 있음",
}


def _study(db, skill, score) -> dict:
    segments = [
        segment
        for resource in skill.resources
        for segment in resource.segments
    ]
    steps = [
        step
        for path in skill.learning_paths
        for step in path.steps
    ]

    done = sum(1 for item in segments + steps if item.status == "completed")

    candidate = today_service._learning_candidate(
        db, {"skill": skill, "priority_score": score}
    )

    return {
        "resources": len(skill.resources),
        "units_done": done,
        "units_total": len(segments) + len(steps),
        "next": candidate["title"] if candidate else None,
        "next_minutes": candidate["minutes"] if candidate else None,
    }


def _stage(level, study, projects, experiences) -> str:
    if experiences:
        return STAGE_COVERED

    if projects:
        return STAGE_BUILDING

    if study["units_done"] > 0 or level > 0:
        return STAGE_STUDYING

    return STAGE_EMPTY


def build_map(db, opportunity) -> dict:
    scores = {
        entry["skill"].id: entry["priority_score"]
        for entry in priority_service.build_skill_priorities(db)
    }

    rows = []

    for skill in opportunity.skills:
        level = skill.level or 0
        score = scores.get(skill.id, 0)
        study = _study(db, skill, score)

        projects = [
            {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "progress_percent": project.progress_percent or 0,
            }
            for project in skill.projects
            if project.career_related
        ]

        experiences = [
            {"id": experience.id, "title": experience.title}
            for experience in skill.experiences
        ]

        stage = _stage(level, study, projects, experiences)

        rows.append({
            "skill_id": skill.id,
            "skill": skill.name,
            "level": level,
            "max_level": priority_service.MAX_SKILL_LEVEL,
            "priority_score": score,
            "study": study,
            "projects": projects,
            "experiences": experiences,
            "stage": stage,
            "stage_label": STAGE_LABELS[stage],
        })

    # 급한 것부터. 점수가 같으면 덜 찬 칸이 위로 온다.
    order = [STAGE_EMPTY, STAGE_STUDYING, STAGE_BUILDING, STAGE_COVERED]
    rows.sort(key=lambda row: (-row["priority_score"], order.index(row["stage"])))

    count = {stage: 0 for stage in order}
    for row in rows:
        count[row["stage"]] += 1

    return {
        "opportunity": {
            "id": opportunity.id,
            "title": opportunity.title,
            "organization": opportunity.organization,
            "source_url": opportunity.source_url,
            # 마감된 공고도 지도는 보여준다 — 무엇이 비어 있었는지는
            # 다음 비슷한 공고에서 그대로 쓸모 있다. 다만 화면이
            # "마감됨" 을 붙일 수 있게 상태를 준다.
            "status": opportunity.status,
            "deadline": opportunity.deadline,
            "days_left": today_service._days_left(
                opportunity.deadline, today_service.date.today()
            ),
        },
        "skills": rows,
        "summary": {
            "total": len(rows),
            "covered": count[STAGE_COVERED],
            "building": count[STAGE_BUILDING],
            "studying": count[STAGE_STUDYING],
            "empty": count[STAGE_EMPTY],
        },
    }
