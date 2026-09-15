"""지원 과정 - Phase 5.

상태 전이와 자소서 작성 지원.

**여기서 하는 "지원" 은 LLM 이 아니다.**
저장된 경험으로 구조를 잡아주고, 기계적으로 확인할 수 있는 것만 확인한다.
문장을 대신 써주는 것은 LLM 이 있어야 하고, 없으면 없다고 말한다.
"""

from .. import models
from . import jd as jd_service


# --------------------------------
# 상태 전이
#
# 규칙이 없으면 "지원함" 에서 "관심 있음" 으로 돌아가는 것도 막지 못한다.
# 다만 잘못 누른 것을 되돌릴 길은 남긴다 (force).
# --------------------------------

TRANSITIONS = {
    "interested": ["preparing", "withdrawn"],
    "preparing": ["ready", "withdrawn"],
    "ready": ["applied", "withdrawn"],
    "applied": ["document_pass", "rejected", "withdrawn"],
    "document_pass": ["interview", "rejected", "withdrawn"],
    "interview": ["accepted", "rejected", "withdrawn"],
    "accepted": [],
    "rejected": [],
    "withdrawn": [],
}

TERMINAL = {"accepted", "rejected", "withdrawn"}

# 이 메시지는 화면에 그대로 뜬다. 'preparing' 같은 원시값을 보이지 않는다.
STATUS_LABELS = {
    "interested": "관심",
    "preparing": "준비 중",
    "ready": "준비 완료",
    "applied": "지원함",
    "document_pass": "서류 통과",
    "interview": "면접",
    "accepted": "합격",
    "rejected": "불합격",
    "withdrawn": "철회",
}


def _label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def allowed_next(status: str) -> list[str]:
    return TRANSITIONS.get(status, [])


def can_move(current: str, target: str) -> bool:
    return target in allowed_next(current)


def describe_transition(current: str, target: str) -> str:
    """왜 막혔는지 설명한다."""
    if current == target:
        return f"이미 '{_label(current)}' 입니다."

    if current in TERMINAL:
        return (
            f"'{_label(current)}' 은(는) 끝난 상태라 더 진행할 수 없습니다. "
            "되돌리려면 force 를 쓰세요."
        )

    options = " / ".join(f"'{_label(option)}'" for option in allowed_next(current))

    return (
        f"'{_label(current)}' 에서는 {options}(으)로만 갈 수 있습니다. "
        "순서를 건너뛰려면 force 를 쓰세요."
    )


# --------------------------------
# 자소서 작성 지원
# --------------------------------

# 이 아래로는 답변이 너무 짧다고 본다 (제한 대비 비율)
TOO_SHORT_RATIO = 0.5


def build_outline(db, application, question) -> dict:
    """이 문항에 쓸 구조를 잡아준다.

    **문장을 만들지 않는다.** 어떤 경험을 어떤 순서로 쓸지만 정한다.
    쓰는 것은 사용자가 한다.
    """
    analysis = jd_service.analyze_application(db, application)

    recommended = analysis["recommended_experiences"]

    if not recommended:
        return {
            "question": question.question,
            "character_limit": question.character_limit,
            "sections": [],
            "message": (
                "이 공고의 요구 역량을 덮는 경험이 Experience Bank 에 없습니다. "
                "관련 없는 경험으로 구조를 짜면 자소서가 더 나빠집니다. "
                "경험을 먼저 등록하세요."
            ),
        }

    top = recommended[0]
    experience = db.get(models.Experience, top["experience_id"])

    limit = question.character_limit or 500

    # 분량 배분은 STAR 비중을 따른다.
    sections = [
        {
            "key": "situation",
            "label": "상황과 과제",
            "source": "Experience.problem",
            "content": (experience.problem or "").strip(),
            "suggested_chars": round(limit * 0.2),
        },
        {
            "key": "role",
            "label": "내 역할",
            "source": "Experience.role",
            "content": (experience.role or "").strip(),
            "suggested_chars": round(limit * 0.15),
        },
        {
            "key": "actions",
            "label": "한 일",
            "source": "Experience.actions",
            "content": (experience.actions or "").strip(),
            "suggested_chars": round(limit * 0.4),
        },
        {
            "key": "results",
            "label": "결과",
            "source": "Experience.results",
            "content": (experience.results or "").strip(),
            "suggested_chars": round(limit * 0.25),
        },
    ]

    empty = [s["label"] for s in sections if not s["content"]]

    message = None

    if empty:
        message = (
            "다음 항목이 Experience 에 비어 있어 채울 내용이 없습니다: "
            + ", ".join(empty)
            + ". 지어내지 않습니다."
        )

    return {
        "question": question.question,
        "character_limit": question.character_limit,
        "based_on": {
            "experience_id": experience.id,
            "title": experience.title,
            "score": top["score"],
            "covered": top["covered"],
        },
        "sections": sections,
        "message": message,
    }


def review_answer(db, question, draft: str) -> dict:
    """쓴 글을 기계적으로 점검한다.

    문체나 설득력은 판단하지 않는다. 그건 LLM 이 있어야 한다.
    여기서는 셀 수 있는 것과 대조할 수 있는 것만 본다.
    """
    text = draft or ""
    length = len(text)
    limit = question.character_limit

    checks = []

    if limit:
        if length > limit:
            checks.append({
                "key": "length",
                "ok": False,
                "message": f"{limit}자 제한을 {length - limit}자 넘었습니다.",
            })
        elif length < limit * TOO_SHORT_RATIO:
            checks.append({
                "key": "length",
                "ok": False,
                "message": (
                    f"{length}/{limit}자 — 제한의 절반도 쓰지 않았습니다."
                ),
            })
        else:
            checks.append({
                "key": "length",
                "ok": True,
                "message": f"{length}/{limit}자.",
            })
    else:
        checks.append({
            "key": "length",
            "ok": True,
            "message": f"{length}자 (제한 없음).",
        })

    # 저장된 경험을 실제로 언급했는가
    experiences = db.query(models.Experience).all()

    mentioned = [
        e.title for e in experiences
        if e.title and e.title.lower() in text.lower()
    ]

    checks.append({
        "key": "grounded",
        "ok": bool(mentioned),
        "message": (
            "언급한 경험: " + ", ".join(mentioned)
            if mentioned
            else "Experience Bank 의 경험이 언급되지 않았습니다."
        ),
    })

    # 구체적인 숫자가 있는가
    import re

    has_number = bool(re.search(r"\d", text))

    checks.append({
        "key": "specific",
        "ok": has_number,
        "message": (
            "구체적인 수치가 있습니다."
            if has_number
            else "수치가 없습니다. 있으면 설득력이 올라갑니다."
        ),
    })

    return {
        "length": length,
        "character_limit": limit,
        "checks": checks,
        "passed": sum(1 for c in checks if c["ok"]),
        "total": len(checks),
        "note": (
            "글자 수와 근거 유무만 확인합니다. "
            "문체와 설득력은 판단하지 않습니다."
        ),
    }
