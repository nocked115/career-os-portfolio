"""지원서 보드 — "그래서 지금 무엇을 해야 하지?"

Applications 화면은 지원서마다 전이 API 를 따로 부르고, 목록에는 상태
칩만 있었다. 무엇을 해야 하는지는 지원서를 하나씩 열어 봐야 알았다.

여기서 지원서마다 한 번에 모은다 — 마감 · 요구 역량 매칭 · 자소서 진행 ·
다음 행동. 상태 전이 규칙과 같은 서버에서 정해야 목록 · Workspace ·
맨 위 요약이 서로 다른 말을 하지 않는다.

**셀 수 있는 것으로만 정한다.**

- 마감      지원서에 적은 날. 없으면 공고의 마감.
- 매칭      JD 에서 찾은 요구 역량 중 스킬 레벨이 1 이상인 것의 개수. 분모와 함께.
- 자소서    저장된 답이 비어 있지 않은 문항 수. 분모와 함께.

정보가 모자라면 다음 행동을 지어내지 않고 모자라다고 말한다.
"""

from datetime import date, datetime

from .. import models
from . import application as application_service
from . import jd as jd_service


# "이번 주" 에 걸리는 마감. Today 의 D-day 띠(14일)보다 좁고,
# 계획 맨 앞으로 끌어올리는 기준(3일)보다 넓다.
URGENT_DAYS = 7

BEFORE_APPLYING = ("interested", "preparing", "ready")
AFTER_APPLYING = ("applied", "document_pass", "interview")

# 맨 위 요약의 "다음 행동" 으로 고를 수 있는 것.
# 결과를 기다리는 것은 행동이 아니다.
ACTIONABLE = ("write", "revise", "add_questions", "move", "submit")


def _as_date(value):
    if value is None:
        return None

    return value.date() if isinstance(value, datetime) else value


def _label(status: str) -> str:
    return application_service.STATUS_LABELS.get(status, status)


def _target(application) -> dict:
    """지원서가 가리키는 공고. Opportunity 가 기본이고 Job 은 예전 경로다."""
    if application.opportunity is not None:
        posting = application.opportunity

        return {
            "kind": "opportunity",
            "title": posting.title,
            "organization": posting.organization or "",
            "source_url": posting.source_url or "",
            "deadline": posting.deadline,
        }

    if application.legacy_job is not None:
        job = application.legacy_job

        return {
            "kind": "legacy_job",
            "title": job.title,
            "organization": getattr(job, "company", "") or "",
            "source_url": getattr(job, "url", "") or "",
            "deadline": None,
        }

    return {
        "kind": "none",
        "title": "지원서",
        "organization": "",
        "source_url": "",
        "deadline": None,
    }


def _match(analysis: dict) -> dict:
    """백분율 하나가 아니라 분모와 근거를 같이 준다."""
    required = analysis["required_skills"]

    if not required:
        notes = analysis["notes"]

        return {
            "available": False,
            "reason": notes[0] if notes else "요구 역량을 찾지 못했습니다.",
            "basis": analysis.get("basis", "text"),
            "total": 0,
            "have": 0,
            "weighted_score": None,
            "skills": [],
        }

    backed = {
        skill
        for experience in analysis["recommended_experiences"]
        for skill in experience["covered"]
    }

    return {
        "available": True,
        "reason": None,
        "basis": analysis.get("basis", "text"),
        "total": len(required),
        "have": sum(1 for item in required if item["strength"] != "gap"),
        "weighted_score": analysis["match_score"],
        "skills": [
            {
                "skill": item["skill"],
                "level": item["my_level"],
                "strength": item["strength"],
                "mentions": item["mentions"],
                "backed": item["skill"] in backed,
            }
            for item in required
        ],
    }


def _letter(application) -> dict:
    questions = sorted(
        application.cover_letter_questions, key=lambda item: item.position
    )

    rows = []

    for number, question in enumerate(questions, start=1):
        current = next(
            (answer for answer in question.answers if answer.is_current), None
        )

        # 공백만 저장한 답은 쓴 것이 아니다.
        written = current is not None and current.draft.strip() != ""

        rows.append({
            "question_id": question.id,
            "number": number,
            "question": question.question,
            "character_limit": question.character_limit,
            "length": len(current.draft) if written else 0,
            "answered": written,
            "version": current.version if current else None,
            "updated_at": current.updated_at if current else None,
        })

    return {
        "total": len(rows),
        "answered": sum(1 for row in rows if row["answered"]),
        "questions": rows,
    }


def _next_action(status, days_left, letter, source_url) -> dict | None:
    """지금 이 지원서에서 할 한 가지.

    순서가 곧 규칙이다 — 끝남 → 기다림 → 마감 지남 → 문항 없음 →
    안 쓴 문항 → 짧은 문항 → 상태 옮기기 → 제출.
    """
    if status in application_service.TERMINAL:
        return None

    if status in ("applied", "document_pass"):
        return {
            "kind": "wait",
            "label": "결과 기다리기",
            "detail": "결과가 나오면 상태를 바꾸세요.",
        }

    if status == "interview":
        return {
            "kind": "interview",
            "label": "면접 준비",
            "detail": "추천 경험과 저장한 자기소개서를 다시 읽어 두세요.",
        }

    if days_left is not None and days_left < 0:
        return {
            "kind": "overdue",
            "label": "마감이 지났습니다",
            "detail": "지원하지 못했다면 철회로 정리하세요.",
        }

    if letter["total"] == 0:
        return {
            "kind": "add_questions",
            "label": "자기소개서 문항 등록",
            "detail": "공고의 문항을 그대로 옮겨 적으세요.",
        }

    for row in letter["questions"]:
        if not row["answered"]:
            return {
                "kind": "write",
                "label": f"{row['number']}번 문항 작성",
                "detail": row["question"],
                "question_id": row["question_id"],
            }

    for row in letter["questions"]:
        limit = row["character_limit"]

        if limit and row["length"] < limit * application_service.TOO_SHORT_RATIO:
            return {
                "kind": "revise",
                "label": f"{row['number']}번 문항 보완",
                "detail": (
                    f"{row['length']}/{limit}자 — 제한의 절반보다 짧습니다."
                ),
                "question_id": row["question_id"],
            }

    if status == "ready":
        return {
            "kind": "submit",
            "label": "지원서 제출",
            "detail": (
                "공고에서 제출한 뒤 상태를 '지원함'으로 바꾸세요."
                if source_url
                else "공고 링크가 없습니다. 제출한 뒤 상태를 '지원함'으로 바꾸세요."
            ),
            "target_status": "applied",
        }

    target = "preparing" if status == "interested" else "ready"

    return {
        "kind": "move",
        "label": f"'{_label(target)}'(으)로 옮기기",
        "detail": f"문항 {letter['total']}개를 모두 썼습니다.",
        "target_status": target,
    }


def build_card(db, application, today: date) -> dict:
    target = _target(application)

    deadline = application.deadline or target["deadline"]

    if application.deadline is not None:
        deadline_source = "application"
    elif target["deadline"] is not None:
        deadline_source = "opportunity"
    else:
        deadline_source = None

    days_left = (
        (_as_date(deadline) - today).days if deadline is not None else None
    )

    analysis = jd_service.analyze_application(db, application)
    letter = _letter(application)

    missing = []

    if deadline is None:
        missing.append("deadline")
    if not analysis["has_description"]:
        missing.append("description")
    if letter["total"] == 0:
        missing.append("questions")

    stamps = [application.updated_at] + [
        row["updated_at"] for row in letter["questions"] if row["updated_at"]
    ]

    return {
        "id": application.id,
        "status": application.status,
        "status_label": _label(application.status),
        "allowed": application_service.allowed_next(application.status),
        "is_terminal": application.status in application_service.TERMINAL,
        "target": target["kind"],
        "opportunity_id": application.opportunity_id,
        "title": target["title"],
        "organization": target["organization"],
        "source_url": target["source_url"],
        "deadline": deadline,
        "deadline_source": deadline_source,
        "days_left": days_left,
        "match": _match(analysis),
        "letter": letter,
        "next_action": _next_action(
            application.status, days_left, letter, target["source_url"]
        ),
        "missing": missing,
        "updated_at": max(stamp for stamp in stamps if stamp is not None),
    }


def _group(card) -> int:
    if card["status"] in BEFORE_APPLYING:
        return 0
    if card["status"] in AFTER_APPLYING:
        return 1
    return 2


def _deadline_order(card):
    days = card["days_left"]

    # 다가오는 마감 → 마감 지남 → 마감일 없음
    return (days is None, days is not None and days < 0, days or 0)


def build_board(db, today: date | None = None) -> dict:
    today = today or date.today()

    applications = db.query(models.Application).all()
    cards = [build_card(db, application, today) for application in applications]

    active = [card for card in cards if not card["is_terminal"]]
    before = [card for card in active if card["status"] in BEFORE_APPLYING]

    urgent = [
        card for card in before
        if card["days_left"] is not None and 0 <= card["days_left"] <= URGENT_DAYS
    ]

    writing = [
        card for card in before
        if 0 < card["letter"]["total"]
        and card["letter"]["answered"] < card["letter"]["total"]
    ]

    candidates = [
        card for card in before
        if card["next_action"] and card["next_action"]["kind"] in ACTIONABLE
    ]
    candidates.sort(key=lambda card: (_deadline_order(card), -card["id"]))

    top = candidates[0] if candidates else None

    cards.sort(key=lambda card: (_group(card), _deadline_order(card), -card["id"]))

    return {
        "today": today,
        "urgent_days": URGENT_DAYS,
        "summary": {
            "active": len(active),
            "before_applying": len(before),
            "urgent": len(urgent),
            "writing": len(writing),
            # 고를 근거가 없으면 비워 둔다. 화면이 "정보가 부족하다" 고 말한다.
            "next": (
                {
                    "application_id": top["id"],
                    "title": top["title"],
                    "organization": top["organization"],
                    "days_left": top["days_left"],
                    **top["next_action"],
                }
                if top
                else None
            ),
        },
        "applications": cards,
    }
