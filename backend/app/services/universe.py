"""Career Universe — 홈에 놓을 것.

DESIGN.md 1~4d 장.

가운데는 나, 궤도의 천체는 커리어를 이루는 영역. 천체를 고르면 바로
들어가지 않고 요약을 한 번 거친다. 클릭하면 즉시 이동인 건 그냥
메뉴다. 요약을 거치면 **선택**이 된다.

여기서 새로 계산하는 것은 없다. 각 서비스가 이미 내놓는 값을 모은다.

`why` 의 모든 줄에는 그 판단의 근거가 된 **실제 숫자**를 붙인다.
"Job Market: HIGH" 만 있으면 확인할 방법이 없고, 확인할 수 없는 것은
근거가 아니다 (원칙 1).
"""

from datetime import date

from .. import models
from . import evidence as evidence_service
from . import learning as learning_service
from . import library as library_service
from . import priority as priority_service
from . import profile as profile_service
from . import proof as proof_service
from . import today as today_service

HIGH = "high"
MID = "mid"
LOW = "low"

TERMINAL_APPLICATION_STATUS = ("accepted", "rejected", "withdrawn")


def _readiness(db):
    """중앙 구체의 퍼센트.

    "커리어 68% 완료" 같은 숫자는 만들지 않는다. 커리어에 완료율은
    없고, 그런 숫자는 근거를 댈 수 없다.

    대신 **목표 직무 스킬의 평균 숙련도**를 쓴다. 이건 설명할 수 있다 —
    레벨 0~4 를 백분율로 바꿔 평균한 값이다. 화면은 이 값 옆에
    무엇의 퍼센트인지 반드시 같이 쓴다.
    """
    target = priority_service.get_active_target_career(db)

    skills = list(target.skills) if target else []
    basis = f"{target.title} 스킬" if target else None

    if not skills:
        skills = db.query(models.Skill).all()
        basis = "등록된 스킬"

    if not skills:
        return {
            "percent": 0,
            "basis": "등록된 스킬이 없습니다",
            "skill_count": 0,
            "detail": "스킬을 등록하면 준비도를 계산합니다.",
        }

    total = sum(
        min(skill.level or 0, priority_service.MAX_SKILL_LEVEL)
        for skill in skills
    )
    percent = round(
        total / (len(skills) * priority_service.MAX_SKILL_LEVEL) * 100
    )

    return {
        "percent": percent,
        "basis": basis,
        "skill_count": len(skills),
        "detail": (
            f"{basis} {len(skills)}개의 평균 숙련도입니다 "
            f"(레벨 0~{priority_service.MAX_SKILL_LEVEL} 기준)."
        ),
    }


def _why(label, level, detail):
    """WHY 한 줄. detail 없이는 만들지 않는다."""
    return {"label": label, "level": level, "detail": detail}


def _stat(key, value, sub=None):
    return {"key": key, "value": value, "sub": sub}


def _band(value, high_at, mid_at):
    """숫자를 세 단계로. 기준을 코드에 드러내 둔다."""
    if value >= high_at:
        return HIGH
    if value >= mid_at:
        return MID
    return LOW


# --------------------------------
# 천체별 요약
# --------------------------------

def _learning(db, entry, skill):
    step = learning_service.find_next_step(skill) if skill else None
    resources = (
        library_service.list_library(db, skill_id=skill.id) if skill else []
    )

    if entry is None:
        # 스킬이 하나도 없을 때. 빈 칸을 만들되 배지는 비우지 않는다.
        return [], [], "스킬 없음"

    total_demand = entry["total_demand"]
    demand_count = entry["demand_count"]
    progress = entry["learning_progress"]

    why = [
        _why(
            "시장 수요",
            HIGH if demand_count > 0 else LOW,
            f"모아둔 기회 {total_demand}건 중 {demand_count}건"
            if total_demand
            else "모아둔 기회 없음",
        ),
        _why(
            "스킬 격차",
            _band(entry["skill_gap"], high_at=3, mid_at=2),
            f"레벨 {entry['my_level']} · 목표까지 {entry['skill_gap']}단계",
        ),
        _why(
            "남은 학습",
            _band(100 - progress, high_at=60, mid_at=30),
            f"경로 진행률 {progress}%",
        ),
    ]

    stats = [
        _stat(
            "다음 학습",
            step.title if step else "다음 단계 없음",
            f"{step.estimated_minutes}분"
            if step and step.estimated_minutes
            else None,
        ),
        _stat("진행률", f"{skill.name} {progress}%" if skill else "—"),
        _stat("내 자료", f"{len(resources)}개"),
    ]

    badge = (
        f"{len(resources)}개 자료" if resources else "자료 없음"
    )

    return why, stats, badge


def _projects(db):
    projects = (
        db.query(models.Project)
        .filter(models.Project.career_related.is_(True))
        .all()
    )

    running = [p for p in projects if not proof_service.is_complete(p)]

    # 끝냈는데 보여줄 것이 없는 프로젝트 — 증거가 되다 만 상태.
    thin = [
        p
        for p in projects
        if proof_service.is_complete(p)
        and not (p.github_url or p.demo_url or p.results)
    ]

    first = max(running, key=lambda p: p.progress_percent, default=None)

    why = [
        _why(
            "진행 중",
            _band(len(running), high_at=1, mid_at=1),
            f"커리어 프로젝트 {len(running)}건",
        ),
        _why(
            "증거 공백",
            _band(len(thin), high_at=1, mid_at=1),
            f"끝났는데 보여줄 것이 없는 프로젝트 {len(thin)}건",
        ),
        _why(
            "포트폴리오 가치",
            _band(len(projects), high_at=2, mid_at=1),
            f"전체 커리어 프로젝트 {len(projects)}건",
        ),
    ]

    stats = [
        _stat(
            "진행 중",
            first.name if first else "없음",
            f"{first.progress_percent}%" if first else None,
        ),
        _stat("증거 필요", f"{len(thin)}건"),
        _stat(
            "증명하는 것",
            " · ".join(
                sorted({s.name for p in projects for s in p.skills})
            )
            or "연결된 스킬 없음",
        ),
    ]

    badge = (
        f"{len(running)}개 진행 중" if running else "진행 중 없음"
    )

    return why, stats, badge


def _opportunities(db, today):
    items = db.query(models.Opportunity).all()

    # 저장된 점수를 읽는다. 여기서 다시 채점하면 홈을 열 때마다
    # 데이터를 쓰게 된다 — 조회가 조용히 쓰기가 되면 안 된다.
    scored = [item for item in items if item.match_score is not None]
    worth = [
        item
        for item in scored
        if item.match_recommendation in ("recommended", "consider")
    ]
    top = max(scored, key=lambda item: item.match_score, default=None)

    deadlines = [
        entry
        for entry in today_service.collect_deadlines(db, today)
        if entry["kind"] == "opportunity"
    ]

    why = [
        _why(
            "볼 가치 있는 것",
            _band(len(worth), high_at=1, mid_at=1),
            f"수집 {len(items)}건 중 {len(worth)}건",
        ),
        _why(
            "마감 임박",
            _band(len(deadlines), high_at=1, mid_at=1),
            f"기한 안에 든 기회 {len(deadlines)}건",
        ),
        _why(
            "채점 안 됨",
            _band(len(items) - len(scored), high_at=1, mid_at=1),
            f"아직 점수 없는 기회 {len(items) - len(scored)}건",
        ),
    ]

    stats = [
        _stat("모은 기회", f"{len(items)}건", f"볼 가치 {len(worth)}건"),
        _stat(
            "가장 잘 맞는 것",
            top.title if top else "없음",
            f"{round(top.match_score)}%" if top else None,
        ),
        _stat(
            "미뤄도 되는 것",
            f"{len(scored) - len(worth)}건",
            "지금은 무시해도 됩니다"
            if len(scored) > len(worth)
            else None,
        ),
    ]

    badge = (
        f"볼 만한 것 {len(worth)}건" if worth
        else f"{len(items)}건 수집" if items
        else "수집 없음"
    )

    return why, stats, badge


def _experience(db):
    stars = evidence_service.build_evidence(db)

    experiences = db.query(models.Experience).count()
    portfolio = db.query(models.PortfolioEntry).count()

    # 완료했는데 아직 Experience 로 옮기지 않은 프로젝트
    waiting = [
        project
        for project in db.query(models.Project).all()
        if proof_service.is_complete(project)
        and proof_service.existing_experience(db, project) is None
    ]

    why = [
        _why(
            "정리 안 된 것",
            _band(len(waiting), high_at=1, mid_at=1),
            f"완료했는데 증거로 안 남은 프로젝트 {len(waiting)}건",
        ),
        _why(
            "쌓인 증거",
            _band(stars["total"], high_at=5, mid_at=2),
            f"별 {stars['total']}개",
        ),
        _why(
            "포트폴리오",
            _band(portfolio, high_at=3, mid_at=1),
            f"항목 {portfolio}건",
        ),
    ]

    stats = [
        _stat(
            "쌓인 증거",
            f"{stars['total']} ★",
            " · ".join(
                f"{item['label']} {item['count']}"
                for item in stars["breakdown"]
                if item["count"] > 0
            )
            or "아직 없음",
        ),
        _stat("정리 대기", f"{len(waiting)}건"),
        _stat("경험 창고", f"{experiences}건", f"포트폴리오 {portfolio}건"),
    ]

    badge = f"★ {stars['total']}"

    return why, stats, badge


def _applications(db, today):
    items = db.query(models.Application).all()

    live = [
        item
        for item in items
        if item.status not in TERMINAL_APPLICATION_STATUS
    ]

    deadlines = [
        entry
        for entry in today_service.collect_deadlines(db, today)
        if entry["kind"] == "application"
    ]
    nearest = deadlines[0] if deadlines else None

    questions = db.query(models.CoverLetterQuestion).count()
    answered = (
        db.query(models.CoverLetterAnswer)
        .filter(models.CoverLetterAnswer.is_current.is_(True))
        .count()
    )

    why = [
        _why(
            "진행 중",
            _band(len(live), high_at=1, mid_at=1),
            f"끝나지 않은 지원 {len(live)}건",
        ),
        _why(
            "마감 임박",
            HIGH if nearest and nearest["days_left"] <= 3 else
            MID if nearest else LOW,
            f"가장 가까운 마감 D-{nearest['days_left']}"
            if nearest
            else "기한 안에 든 지원 없음",
        ),
        _why(
            "자소서",
            _band(questions - answered, high_at=1, mid_at=1),
            f"문항 {questions}개 중 {answered}개 작성",
        ),
    ]

    stats = [
        _stat("진행 중", f"{len(live)}건", f"전체 {len(items)}건"),
        _stat(
            "가장 가까운 마감",
            f"D-{nearest['days_left']}" if nearest else "없음",
            nearest["title"] if nearest else None,
        ),
        _stat("자기소개서", f"{answered} / {questions} 문항"),
    ]

    badge = (
        f"{len(live)}건 진행 중" if live else "진행 중 없음"
    )

    return why, stats, badge


def _library(db, available_minutes):
    summary = library_service.summarize(db)
    selection = library_service.select_for_today(db, available_minutes)

    owned = summary["by_ownership"].get("owned", 0)
    picked = len(selection["selected"])
    aside = selection["set_aside_count"]

    why = [
        _why(
            "지금 필요한 것",
            _band(picked, high_at=1, mid_at=1),
            f"{picked}개 · {selection['selected_minutes']}분",
        ),
        _why(
            "안 봐도 되는 것",
            _band(aside, high_at=3, mid_at=1),
            f"{aside}개는 지금 아님",
        ),
        _why(
            "내가 가진 것",
            _band(owned, high_at=3, mid_at=1),
            f"보유 {owned}개 · 전체 {summary['total']}개",
        ),
    ]

    stats = [
        _stat(
            "가진 자료",
            f"{owned}개",
            f"저장 {summary['by_ownership'].get('saved', 0)}개",
        ),
        _stat(
            "지금 필요",
            f"{picked}개",
            f"나머지 {aside}개는 지금 아님" if aside else None,
        ),
        _stat(
            "챕터",
            f"{summary['segments_done']} / {summary['segments']}",
            "조각 완료",
        ),
    ]

    badge = f"{picked}개 필요 · {aside}개 보류"

    return why, stats, badge


# --------------------------------
# 조립
# --------------------------------

# 천체는 이름이 약속한 곳에 도착해야 한다.
# 화면(route)만으로는 부족해서 그 안의 어디인지(section)까지 준다 —
# MY LIBRARY 를 눌렀는데 학습 경로가 열리면 고른 것과 다른 데 온 것이다.
PLANETS = (
    ("learning", "LEARNING", "학습 · 내 자료", "learning", "paths"),
    ("projects", "PROJECTS", "만들기 · 증거", "projects", None),
    (
        "opportunities",
        "OPPORTUNITIES",
        "기회 · 공고 · 공모전",
        "opportunities",
        None,
    ),
    ("experience", "EXPERIENCE", "경험 · 포트폴리오", "proof", None),
    ("applications", "APPLICATIONS", "지원 · 자기소개서", "applications", None),
    ("library", "MY LIBRARY", "내가 가진 것", "library", None),
)


def build_universe(
    db,
    today: date | None = None,
    available_minutes: int | None = None,
) -> dict:
    """홈 한 장에 필요한 것 전부."""
    today = today or date.today()
    minutes = (
        available_minutes
        if available_minutes is not None
        else today_service.DEFAULT_AVAILABLE_MINUTES
    )

    entries = priority_service.build_skill_priorities(db)
    entry = entries[0] if entries else None
    skill = entry["skill"] if entry else None

    plan = today_service.build_plan(db, today=today, available_minutes=minutes)

    builders = {
        "learning": lambda: _learning(db, entry, skill),
        "projects": lambda: _projects(db),
        "opportunities": lambda: _opportunities(db, today),
        "experience": lambda: _experience(db),
        "applications": lambda: _applications(db, today),
        "library": lambda: _library(db, minutes),
    }

    planets = []

    for key, name, ko, route, section in PLANETS:
        why, stats, badge = builders[key]()

        planets.append({
            "key": key,
            "name": name,
            "ko": ko,
            "route": route,
            "section": section,
            "badge": badge,
            "why": why,
            "stats": stats,
        })

    return {
        "date": today,
        "me": profile_service.build_profile(db, today),
        "today": {
            "available_minutes": plan["available_minutes"],
            "planned_minutes": plan["planned_minutes"],
            "total_tasks": plan["total_tasks"],
            "done_tasks": plan["done_tasks"],
            # 개수만으로는 "오늘 뭘 하면 되지?" 에 답이 안 된다. 첫 할 일을 준다.
            "first_task": next(
                (
                    {"title": t["title"], "minutes": t["minutes"], "area": t["area"]}
                    for t in plan["tasks"]
                    if t["status"] == "planned"
                ),
                None,
            ),
        },
        # 배경의 별은 장식이 아니라 쌓인 증거의 실제 개수다.
        "readiness": _readiness(db),
        "evidence": evidence_service.build_evidence(db),
        "planets": planets,
    }
