"""Why this plan? — 오늘 계획이 나온 근거를 한곳에 모은다.

DESIGN.md 원칙 1: 근거 없는 추천은 없다.

여기서 **새로 계산하는 것은 없다.** 이미 각 서비스가 내놓고 있는 값을
모으기만 한다. 계산이 두 곳에 생기면 화면과 계획이 서로 다른 말을
하게 된다 (CODEX_HANDOFF 의 반복된 함정).

근거가 없는 칸은 비었다고 말한다. 채워 넣지 않는다.
"""

from datetime import date

from . import learning as learning_service
from . import library as library_service
from . import market as market_service
from . import priority as priority_service
from . import calendar as calendar_service
from . import today as today_service


# 각 입력을 알아보게 하는 표식. 화면에서 아이콘 자리에 놓인다.
# 화면 1단계에서 쓸 말. 영문 라벨(MARKET, SKILL GAP)은 계산 용어라
# 결론을 보러 온 사람에게는 읽히지 않는다.
KOREAN = {
    "target": "목표 직무",
    "market": "시장 수요",
    "gap": "내 수준",
    "project": "프로젝트",
    "learning": "학습",
    "library": "내 자료",
    "deadline": "마감",
    "time": "오늘 시간",
}

GLYPHS = {
    "target": "◎",
    "market": "▤",
    "gap": "△",
    "project": "▲",
    "learning": "◈",
    "library": "▣",
    "deadline": "◷",
    "time": "◔",
}


# 근거 문장에 원시값(in_progress, official_doc, owned)을 섞지 않는다.
STEP_STATUS = {
    "not_started": "시작 전",
    "in_progress": "진행 중",
    "completed": "완료",
    "review_needed": "복습 필요",
}

RESOURCE_TYPES = {
    "official_doc": "공식 문서",
    "documentation": "문서",
    "book": "책",
    "course": "강의",
    "video": "영상",
    "youtube": "영상",
    "article": "글",
    "paper": "논문",
    "practice": "실습",
}

OWNERSHIP = {
    "owned": "가지고 있음",
    "saved": "저장함",
    "wishlist": "살 목록",
}


def _dday(days: int) -> str:
    return "오늘 마감" if days == 0 else f"D-{days}"


def _cell(key, label, value, detail, available=True, evidence=None):
    """판단에 쓰인 입력 한 칸.

    available=False 는 "데이터가 없어서 이 입력은 판단에 못 썼다" 는 뜻이다.
    화면은 이걸 흐리게 그려서 무엇이 빠졌는지 보여준다.

    evidence 는 그 문장이 어디서 나왔는지 — 펼쳤을 때 보이는 원본
    숫자다. 펼쳐서 보여줄 게 없으면 화살표는 장식이 된다.
    """
    return {
        "key": key,
        "label": label,
        "glyph": GLYPHS.get(key, "·"),
        "ko": KOREAN.get(key, label),
        "value": value,
        "detail": detail,
        "available": available,
        "evidence": evidence or [],
    }


def _target_cell(db):
    target = priority_service.get_active_target_career(db)

    if target is None:
        return _cell(
            "target", "TARGET",
            "설정 안 함",
            "목표 직무를 정하면 그 직무의 스킬에 가중치가 붙습니다.",
            available=False,
        )

    return _cell(
        "target", "TARGET",
        target.title,
        "목표 직무가 모든 판단의 기준점입니다.",
        evidence=[
            f"목표 직무 · {target.title}",
            f"연결된 스킬 {len(target.skills)}개",
            "목표 스킬은 우선순위 가중치 1.0, 무관한 스킬은 0.6",
        ],
    )


def _market_cell(db, entry, skill):
    total_demand = entry["total_demand"]

    if total_demand == 0:
        return _cell(
            "market", "MARKET",
            "모아둔 기회 없음",
            "공고·공모전을 모으면 수요를 근거로 쓸 수 있습니다.",
            available=False,
        )

    return _cell(
        "market", "MARKET",
        f"{skill.name} · {entry['demand_count']} / {total_demand}",
        f"모아둔 기회 {total_demand}건 중 {entry['demand_count']}건이 "
        f"{skill.name} 을(를) 요구합니다.",
        evidence=[
            f"모아둔 기회 {total_demand}건 (공고 · 인턴 · 공모전 · 활동)",
        ] + [
            f"{item['skill']} · {item['opportunity_count']} / {total_demand}건"
            for item in market_service.build_signals(db)
            if item["opportunity_count"] > 0
        ] + [
            f"{skill.name} 비율 {entry['market_percentage']}%",
            "이 값이 우선순위 점수에 그대로 곱해집니다",
            "채용 시장 전체가 아니라 내가 모아둔 것만 봅니다",
        ],
    )


def _gap_cell(entry):
    return _cell(
        "gap", "SKILL GAP",
        f"레벨 {entry['my_level']} · 목표까지 {entry['skill_gap']}단계",
        "현재 레벨과 목표 사이 격차가 가장 큰 스킬을 고릅니다.",
        evidence=[
            f"현재 레벨 {entry['my_level']}",
            f"목표 레벨 {priority_service.MAX_SKILL_LEVEL}",
            f"격차 {entry['skill_gap']}단계",
            "격차가 0 이면 우선순위도 0 이 됩니다",
        ],
    )


def _project_cell(entry):
    projects = entry["career_projects"]

    if not projects:
        return _cell(
            "project", "PROJECT",
            "관련 프로젝트 없음",
            "이 스킬을 쓰는 커리어 프로젝트가 없습니다.",
            available=False,
        )

    first = projects[0]

    return _cell(
        "project", "PROJECT",
        f"{first.progress_percent}%",
        " · ".join(project.name for project in projects),
        evidence=[
            f"{project.name} · {project.progress_percent}%"
            for project in projects
        ] + [
            f"증거 세기 {entry['project_strength']}"
            f" (학습 {entry['learning_strength']} 과 합쳐 "
            f"{entry['evidence_strength']})",
            "만들기로 한 것 0.10 · 만드는 중 0.25 · 만들었다 0.50 · "
            "보여줄 수 있다 0.70 · 경험으로 남았다 0.85",
            "증거가 셀수록 그 스킬을 새로 배울 필요는 줄어듭니다",
        ],
    )


def _learning_cell(db, skill):
    step = learning_service.find_next_step(skill)

    if step is None:
        return _cell(
            "learning", "LEARNING",
            "학습 경로 없음",
            "경로를 만들면 다음 단계를 계획에 넣습니다.",
            available=False,
        )

    return _cell(
        "learning", "LEARNING",
        step.title,
        f"{step.learning_path.title} 에서 아직 끝나지 않은 첫 단계입니다.",
        evidence=[
            f"경로 · {step.learning_path.title}",
            f"경로 진행률 {step.learning_path.progress_percent}%",
            f"이 단계 상태 · {STEP_STATUS.get(step.status, step.status)}",
            (
                f"예상 {step.estimated_minutes}분"
                if step.estimated_minutes
                else "예상 시간이 없어 오늘 계획에 넣기 어렵습니다"
            ),
        ],
    )


def _library_cell(db, skill):
    resources = library_service.list_library(db, skill_id=skill.id)

    if not resources:
        return _cell(
            "library", "MY LIBRARY",
            "관련 자료 없음",
            "가진 자료를 등록하면 그중에서 골라 씁니다.",
            available=False,
        )

    kinds = {}
    for resource in resources:
        kinds[resource["resource_type"]] = (
            kinds.get(resource["resource_type"], 0) + 1
        )

    detail = " · ".join(
        f"{RESOURCE_TYPES.get(kind, '기타')} {count}"
        for kind, count in sorted(kinds.items())
    )

    return _cell(
        "library", "MY LIBRARY",
        f"관련 자료 {len(resources)}개",
        detail,
        evidence=[
            f"{resource['title']} · "
            f"{OWNERSHIP.get(resource['ownership'], resource['ownership'])}"
            for resource in resources[:6]
        ] + (
            [f"그 밖 {len(resources) - 6}개"] if len(resources) > 6 else []
        ),
    )


def _deadline_cell(db, today):
    deadlines = today_service.collect_deadlines(db, today)

    if not deadlines:
        # "없음" 도 판단이다. 무엇을 보고 없다고 했는지 적는다.
        return _cell(
            "deadline", "DEADLINES",
            "임박한 것 없음",
            "3일 이내 마감이 생기면 계획 맨 앞으로 올라옵니다.",
            evidence=[
                f"기한 안({today_service.DEADLINE_HORIZON_DAYS}일)에 든 "
                "마감이 0건입니다",
                "지원서와 기회의 마감일을 함께 봅니다",
                "마감이 없으면 우선순위 순서를 그대로 따릅니다",
            ],
        )

    nearest = deadlines[0]

    return _cell(
        "deadline", "DEADLINES",
        _dday(nearest["days_left"]),
        f"{nearest['title']} · 마감이 가까우면 우선 배치합니다.",
        evidence=[
            f"{_dday(item['days_left'])} · {item['title']}"
            for item in deadlines[:5]
        ],
    )


def _time_cell(db, plan, today):
    """이 숫자가 어디서 나왔는지까지 말한다.

    "120분" 만 있으면 사용자가 정한 값인지 계산된 값인지 알 수 없다.
    """
    day = calendar_service.build_day(db, today)

    evidence = [
        f"활동 시간대 {day['window_label']} · {day['window_minutes']}분",
        f"일정으로 찬 시간 {day['busy_minutes']}분",
        f"비어 있는 시간 {day['free_minutes']}분",
        f"하루 상한 {day['daily_cap_minutes']}분",
        (
            f"→ 캘린더 제안 {day['suggested_minutes']}분"
            + (" (상한에 걸림)" if day["capped"] else "")
        ),
        f"이 계획에 쓴 값 {plan['available_minutes']}분",
        f"계획된 시간 {plan['planned_minutes']}분 · "
        f"남은 시간 {plan['remaining_minutes']}분",
    ]

    return _cell(
        "time", "AVAILABLE TIME",
        f"{plan['available_minutes']}분",
        f"강도 {plan['intensity_label']} · 이 시간 안에서 계획을 짭니다.",
        evidence=evidence,
    )


def _limits(cells, plan):
    """이 판단이 못 하는 것. 숨기지 않는다."""
    notes = []

    # 계산 용어(MARKET)가 아니라 화면에 보이는 이름으로 말한다.
    missing = [cell["ko"] for cell in cells if not cell["available"]]
    if missing:
        notes.append(
            "다음 입력은 데이터가 없어 판단에 쓰지 못했습니다: "
            + ", ".join(missing)
            + "."
        )

    if plan["total_tasks"] == 0:
        notes.append(
            "아직 오늘 계획이 없습니다. 아래 근거로 계획을 세울 수 있습니다."
        )

    notes.append(
        "우선순위는 내가 모아둔 기회만으로 계산합니다. "
        "실제 채용 시장 전체를 보지 않습니다."
    )

    return notes


def _headline(entry, skill, plan) -> str:
    """한 줄 결론.

    "그래서 왜?" 에 대한 답이 먼저 와야 한다. 계산에 쓴 입력을
    나열하는 것은 그다음이다.
    """
    if skill is None:
        return "아직 판단할 데이터가 없습니다."

    if plan["total_tasks"] == 0:
        return f"{skill.name} 이(가) 지금 가장 중요합니다."

    return (
        f"{skill.name} 이(가) 지금 가장 중요해서 "
        f"오늘 {plan['total_tasks']}개를 골랐습니다."
    )


def build_why(
    db,
    today: date | None = None,
    available_minutes: int | None = None,
    intensity_name: str | None = None,
) -> dict:
    """오늘 계획의 근거 전체."""
    today = today or date.today()

    entries = priority_service.build_skill_priorities(db)

    if not entries:
        return {
            "date": today,
            "focus_skill": None,
            "headline": "아직 판단할 데이터가 없습니다.",
            "inputs": [],
            "decision": None,
            "limits": ["등록된 스킬이 없어 계획을 세울 수 없습니다."],
        }

    entry = entries[0]
    skill = entry["skill"]

    plan = today_service.build_plan(
        db,
        today=today,
        available_minutes=(
            available_minutes
            if available_minutes is not None
            else today_service.DEFAULT_AVAILABLE_MINUTES
        ),
        intensity_name=intensity_name or today_service.DEFAULT_INTENSITY,
    )

    cells = [
        _target_cell(db),
        _market_cell(db, entry, skill),
        _gap_cell(entry),
        _project_cell(entry),
        _learning_cell(db, skill),
        _library_cell(db, skill),
        _deadline_cell(db, today),
        _time_cell(db, plan, today),
    ]

    used = [cell for cell in cells if cell["available"]]

    return {
        "date": today,
        "focus_skill": skill.name,
        "headline": _headline(entry, skill, plan),
        "priority_score": entry["priority_score"],
        "inputs": cells,
        "used_count": len(used),
        "decision": {
            "tasks": plan["tasks"],
            "planned_minutes": plan["planned_minutes"],
            "available_minutes": plan["available_minutes"],
            "remaining_minutes": plan["remaining_minutes"],
            "total_tasks": plan["total_tasks"],
        },
        "limits": _limits(cells, plan),
    }
