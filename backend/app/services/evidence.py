"""증거 집계 - "Even if you miss, you'll land among the stars."

Career OS 홈의 별은 장식이 아니라 **실제로 쌓은 증거의 개수**다.
그래서 개수를 세는 곳이 한 군데 있어야 한다. 여기다.

무엇을 증거로 세는지는 DESIGN.md 4c 에 고정되어 있다.
화면이 예뻐 보이라고 개수를 늘리지 않는다.
"""

from sqlalchemy import or_

from .. import models


# 프로젝트 완료 판정.
# 기존 코드(main.py, agents/tools.py)가 status == "completed" 로 판단하므로
# 그 기준을 그대로 쓰되, 진행률만 100 으로 올려두고 상태를 안 바꾼 경우도
# 완료로 인정한다. 사용자가 실제로 끝낸 것을 안 세면 개수가 거짓이 된다.
PROJECT_DONE_STATUS = "completed"
PROJECT_DONE_PERCENT = 100

# 지원 결과 중 증거로 세는 상태.
# 떨어진 지원도 별이 된다 — 인용문의 "Even if you miss" 가 그 뜻이다.
REJECTED_STATUS = "rejected"


def _count_completed_learning_steps(db) -> int:
    return (
        db.query(models.LearningStep)
        .filter(models.LearningStep.status == "completed")
        .count()
    )


def _count_completed_projects(db) -> int:
    return (
        db.query(models.Project)
        .filter(
            or_(
                models.Project.status == PROJECT_DONE_STATUS,
                models.Project.progress_percent >= PROJECT_DONE_PERCENT,
            )
        )
        .count()
    )


def _count_experiences(db) -> int:
    return db.query(models.Experience).count()


def _count_portfolio_entries(db) -> int:
    return db.query(models.PortfolioEntry).count()


def _count_rejected_applications(db) -> int:
    return (
        db.query(models.Application)
        .filter(models.Application.status == REJECTED_STATUS)
        .count()
    )


# 순서가 화면 표기 순서다.
SOURCES = (
    ("completed_learning_steps", "완료한 학습 단계", _count_completed_learning_steps),
    ("completed_projects", "완료한 프로젝트", _count_completed_projects),
    ("experiences", "경험", _count_experiences),
    ("portfolio_entries", "포트폴리오", _count_portfolio_entries),
    ("rejected_applications", "떨어진 지원", _count_rejected_applications),
)


def build_evidence(db) -> dict:
    """증거 개수와 그 구성.

    총합만 주면 화면이 숫자의 근거를 설명할 수 없다.
    무엇으로 이루어졌는지 항상 함께 돌려준다.
    """
    breakdown = [
        {"key": key, "label": label, "count": counter(db)}
        for key, label, counter in SOURCES
    ]

    total = sum(item["count"] for item in breakdown)

    return {
        "total": total,
        "is_empty": total == 0,
        "breakdown": breakdown,
    }


def count_total(db) -> int:
    """총 개수만 필요할 때."""
    return sum(counter(db) for _, _, counter in SOURCES)
