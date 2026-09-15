"""PROVE — 한 활동을 취업에 쓸 수 있는 증거로 바꾼다 (Phase 4).

    Project 완료 → Experience Bank → Portfolio → Resume Bullet

지금까지 데이터 구조는 다 있었지만 그 사이를 이어주는 판단이 없었다.
프로젝트를 끝내도 아무 제안이 없으면 사용자는 그냥 잊는다.
**증거화는 자동 제안이 있어야 실제로 일어난다.**

근거 규칙: 저장된 내용에서만 만든다. 없는 성과를 지어내지 않는다.
"""

from .. import models


PROJECT_DONE_STATUS = "completed"
PROJECT_DONE_PERCENT = 100


def is_complete(project) -> bool:
    """진행률만 올리고 상태를 안 바꾼 경우도 완료로 본다."""
    return (
        project.status == PROJECT_DONE_STATUS
        or (project.progress_percent or 0) >= PROJECT_DONE_PERCENT
    )


def existing_experience(db, project):
    """이 프로젝트가 이미 Experience 로 옮겨졌는지.

    "완료했는데 아직 증거로 안 남은 것" 을 세려면 밖에서도 필요하다.
    """
    return (
        db.query(models.Experience)
        .filter(models.Experience.project_id == project.id)
        .first()
    )


def _existing_portfolio(db, project, experience):
    query = db.query(models.PortfolioEntry)

    if experience is not None:
        entry = query.filter(
            models.PortfolioEntry.experience_id == experience.id
        ).first()

        if entry is not None:
            return entry

    return query.filter(
        models.PortfolioEntry.project_id == project.id
    ).first()


def build_suggestions(db, project) -> dict:
    """이 프로젝트가 증명하는 것과, 다음에 할 일.

    완료되지 않은 프로젝트에도 답한다.
    "아직 아니다" 도 정확한 상태다.
    """
    experience = existing_experience(db, project)
    portfolio = _existing_portfolio(db, project, experience)

    proves = [skill.name for skill in project.skills]

    actions = [
        {
            "key": "record_results",
            "label": "결과 기록",
            "done": bool((project.results or "").strip()),
            "hint": "무엇을 이뤘는지 한 줄이라도 남겨야 증거가 된다",
        },
        {
            "key": "add_github_url",
            "label": "GitHub 링크 추가",
            "done": bool((project.github_url or "").strip()),
            "hint": "코드가 있으면 가장 강한 증거다",
        },
        {
            "key": "add_demo_url",
            "label": "데모 링크 추가",
            "done": bool((project.demo_url or "").strip()),
            "hint": "동작하는 것을 보여줄 수 있으면 좋다",
        },
        {
            "key": "save_to_experience",
            "label": "경험으로 저장",
            "done": experience is not None,
            "hint": "자소서를 쓸 때마다 처음부터 떠올리지 않게 된다",
        },
        {
            "key": "prepare_portfolio",
            "label": "포트폴리오 항목 만들기",
            "done": portfolio is not None,
            "hint": "보여줄 수 있는 형태로 다듬는다",
        },
        {
            "key": "generate_resume_bullet",
            "label": "이력서 문장 만들기",
            "done": bool(portfolio and (portfolio.resume_bullet or "").strip()),
            "hint": "저장된 내용에서만 만든다",
        },
    ]

    remaining = [a for a in actions if not a["done"]]

    return {
        "project_id": project.id,
        "project_name": project.name,
        "is_complete": is_complete(project),
        "progress_percent": project.progress_percent or 0,
        "proves": proves,
        "experience_id": experience.id if experience else None,
        "portfolio_entry_id": portfolio.id if portfolio else None,
        "actions": actions,
        "remaining_count": len(remaining),
        # 남은 것 중 첫 번째. 순서가 곧 권하는 순서다.
        "next_action": remaining[0] if remaining else None,
        "message": _message(project, proves, remaining),
    }


def _message(project, proves, remaining) -> str:
    if not is_complete(project):
        return (
            f"진행률 {project.progress_percent or 0}% 입니다. "
            "완료하면 증거로 만들 수 있습니다."
        )

    if not proves:
        return (
            "완료했지만 연결된 스킬이 없어 무엇을 증명하는지 알 수 없습니다. "
            "스킬을 연결해 주세요."
        )

    if not remaining:
        return "증거화가 끝났습니다."

    return (
        f"완료했습니다. 이 프로젝트는 {' · '.join(proves)} 을(를) 증명합니다. "
        f"남은 것 {len(remaining)}가지."
    )


# --------------------------------
# 변환
# --------------------------------

def to_experience(db, project):
    """프로젝트를 Experience 로 옮긴다. 이미 있으면 그것을 쓴다.

    내용을 복사할 뿐 새로 지어내지 않는다.
    """
    existing = existing_experience(db, project)

    if existing is not None:
        return existing, False

    experience = models.Experience(
        experience_type="project",
        title=project.name,
        short_description=project.description or "",
        # problem 은 상황과 과제를 함께 담는다 (아래 설계 결정 참고)
        problem=project.description or "",
        results=project.results or "",
        technologies=", ".join(skill.name for skill in project.skills),
        github_url=project.github_url or "",
        demo_url=project.demo_url or "",
        project_id=project.id,
    )

    experience.skills.extend(project.skills)

    db.add(experience)
    db.commit()
    db.refresh(experience)

    return experience, True


# --------------------------------
# 이력서 문장
#
# LLM 이 아니다. 저장된 조각을 조립할 뿐이다.
# 비어 있는 것은 비었다고 말하고, 채워 넣지 않는다.
# --------------------------------

# 화면에 보이는 이름. 원시 키(results)를 문장에 섞지 않는다.
MISSING_LABELS = {
    "results": "결과",
    "actions": "한 일 · 역할",
    "technologies": "사용 기술",
}


# --------------------------------
# 경험이 어디에 쓰였는가
#
# 경험은 한 번 적고 여러 지원서에 다시 꺼내 쓰는 것이다. 어느 지원서에
# 매칭해 뒀는지 보이지 않으면 재사용된다는 사실 자체가 안 보인다.
# --------------------------------

EXPERIENCE_FIELDS = (
    ("problem", "상황과 과제"),
    ("role", "내 역할"),
    ("actions", "한 일"),
    ("results", "결과"),
    ("metrics", "수치"),
)


def experience_usage(db) -> list[dict]:
    """경험마다 연결된 프로젝트 · 포트폴리오 · 매칭한 지원서 · 비어 있는 칸."""
    rows = []

    for experience in db.query(models.Experience).all():
        applications = []

        for match in experience.application_matches:
            application = match.application

            if application is None:
                continue

            posting = application.opportunity or application.legacy_job

            applications.append({
                "application_id": application.id,
                "title": getattr(posting, "title", None) or "지원서",
                "organization": (
                    getattr(posting, "organization", None)
                    or getattr(posting, "company", None)
                    or ""
                ),
                "status": application.status,
                "match_score": match.match_score,
            })

        rows.append({
            "experience_id": experience.id,
            "project": (
                {"id": experience.project.id, "name": experience.project.name}
                if experience.project
                else None
            ),
            "portfolio_entry_ids": [
                entry.id for entry in experience.portfolio_entries
            ],
            "applications": applications,
            "missing": [
                label
                for key, label in EXPERIENCE_FIELDS
                if not (getattr(experience, key) or "").strip()
            ],
        })

    return rows


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        cleaned = line.strip().lstrip("-*·").strip()
        if cleaned:
            return cleaned
    return ""


def build_resume_bullet(entry) -> dict:
    """포트폴리오 항목에서 이력서 한 줄 초안을 만든다.

    **없는 성과를 지어내지 않는다.**
    재료가 부족하면 문장 대신 무엇이 비었는지 알려준다.
    """
    technologies = (entry.technologies or "").strip()
    role = _first_line(entry.role)
    actions = _first_line(entry.actions)
    results = _first_line(entry.results)

    missing = []

    if not results:
        missing.append("results")
    if not actions and not role:
        missing.append("actions")
    if not technologies:
        missing.append("technologies")

    # 결과와 행동이 둘 다 없으면 문장이 될 수 없다.
    if not results and not actions and not role:
        return {
            "draft": None,
            "missing": missing,
            "message": (
                "무엇을 했고 어떤 결과가 있었는지가 비어 있어 "
                "문장을 만들 수 없습니다. 지어내지 않습니다."
            ),
        }

    parts = []

    if technologies:
        parts.append(f"{technologies} 기반")

    parts.append(entry.title)

    doing = actions or role
    if doing:
        parts.append(f"— {doing}")

    if results:
        parts.append(f"→ {results}")

    draft = " ".join(parts)

    message = None

    if missing:
        message = (
            "비어 있는 항목이 있어 초안이 약합니다: "
            + ", ".join(MISSING_LABELS.get(key, key) for key in missing)
        )

    return {"draft": draft, "missing": missing, "message": message}


def save_resume_bullet(db, entry) -> dict:
    """초안을 만들어 저장한다. 만들 수 없으면 저장하지 않는다."""
    result = build_resume_bullet(entry)
    result["missing_labels"] = [
        MISSING_LABELS.get(key, key) for key in result["missing"]
    ]

    if result["draft"] is None:
        return {**result, "saved": False}

    entry.resume_bullet = result["draft"]
    db.commit()
    db.refresh(entry)

    return {**result, "saved": True}
