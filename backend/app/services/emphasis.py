"""공고가 보는 것 — 그리고 내 어느 경험이 그걸 보여주는가.

수현: "공고 파악하면 우대사항이랑 회사에서 보는 스킬들 · 협업 경험
이런 키워드 너가 알아서 추출해서, 이걸 강조하면 좋아요 이런 것들을
조금 만들어 줄 수 있어?"

지원서 분석(application.analysis)은 **도구**를 뽑는다 — Python, SQL,
PyTorch. 그런데 공고가 보는 것의 절반은 도구가 아니다. "여러
이해관계자와 함께 일하는 것이 즐거운 분", "사실에서 멈추지 않고 진짜
원인을 파고드는 분" 같은 말이 자격요건 옆에 늘 붙어 있는데, 앱은
그것을 통째로 흘려보냈다.

세 가지를 한다.

  구간   자격요건 · 우대사항을 글에서 잘라낸다. 우대사항이 특히 중요한
         까닭은, 거기가 **갈리는 지점**이라서다. 필수는 다들 맞춰 온다.
  결     도구가 아닌 낱말을 센다 — 협업 · 주도 · 문제 정의 · 오너십.
  증거   그 낱말이 들어간 **내 경험과 프로젝트**를 찾아 붙인다.

**지어내지 않는다.** 공고에 없는 말은 만들지 않고, 내 기록에 없으면
"쓸 거리가 없다" 고 한다. 그게 바로 다음에 만들 것이다.
"""
import re

from .. import models
from . import posting_parser


# 도구가 아닌, 회사가 늘 보는 결. 공고마다 말이 조금씩 다르므로 묶어서 센다.
TRAITS = (
    ("협업", "함께 일하기", (
        "협업", "커뮤니케이션", "이해관계자", "유관부서", "소통",
        "팀워크", "크로스", "cross-functional", "collaborat",
    )),
    ("주도", "스스로 움직이기", (
        "주도", "능동", "오너십", "ownership", "자율", "스스로",
        "리드", "lead ", "책임지고",
    )),
    ("문제정의", "문제를 정의하기", (
        "문제 정의", "문제정의", "원인", "가설", "왜", "본질",
        "정의하고", "problem", "근본",
    )),
    ("데이터근거", "근거로 판단하기", (
        "데이터 기반", "데이터로", "정량", "지표", "KPI", "A/B",
        "실험", "검증", "숫자로",
    )),
    ("전달", "설명하고 설득하기", (
        "설명", "보고", "발표", "리포팅", "문서화", "공유",
        "présent", "presentation",
    )),
    ("개선", "끝까지 바꾸기", (
        "개선", "효율", "자동화", "최적화", "운영", "안정화",
    )),
)

SECTION_HEADS = (
    ("required", "자격요건", ("자격요건", "자격 요건", "필수", "지원자격", "requirements")),
    ("preferred", "우대사항", ("우대사항", "우대 사항", "우대", "preferred", "plus")),
)

BULLET = re.compile(r"^[\s□■●○◆◇▶▷\-·*•※]+")


def _lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def sections(text: str) -> list[dict]:
    """자격요건 · 우대사항 구간을 글에서 잘라낸다.

    머리글을 만나면 거기서 시작하고, 다음 머리글이나 빈 줄 뭉치에서
    끊는다. 머리글이 없으면 빈 목록 — 없는 구간을 지어내지 않는다.
    """
    lines = _lines(text)
    found, current = [], None

    for line in lines:
        head = next(
            (
                item for item in SECTION_HEADS
                if any(word in line.lower() for word in item[2])
                and len(line) <= 40
            ),
            None,
        )

        if head is not None:
            current = {"kind": head[0], "label": head[1], "items": []}
            found.append(current)
            continue

        if current is None:
            continue

        # 다른 큰 머리글을 만나면 구간이 끝난 것으로 본다.
        if len(line) <= 20 and line.endswith(("습니다", "요")) is False and ":" in line:
            current = None
            continue

        item = BULLET.sub("", line).strip()

        if item and len(item) <= 200 and len(current["items"]) < 12:
            current["items"].append(item)

    return [row for row in found if row["items"]]


def traits(text: str) -> list[dict]:
    """도구가 아닌 낱말. 몇 번 나왔는지와 그 줄을 같이 돌려준다."""
    lines = _lines(text)
    lowered = (text or "").lower()

    rows = []

    for key, label, words in TRAITS:
        hits = sum(lowered.count(word.lower()) for word in words)

        if not hits:
            continue

        evidence = next(
            (
                line for line in lines
                if any(word.lower() in line.lower() for word in words)
                and len(line) <= 160
            ),
            "",
        )

        rows.append({
            "key": key, "label": label, "mentions": hits, "line": evidence,
        })

    rows.sort(key=lambda row: -row["mentions"])

    return rows


def _my_evidence(db, words) -> list[dict]:
    """그 결을 보여주는 내 경험 · 프로젝트. 내 기록에 있는 말로만 찾는다."""
    found = []

    for experience in db.query(models.Experience).all():
        haystack = " ".join(filter(None, [
            experience.title, experience.short_description, experience.problem,
            experience.role, experience.actions, experience.results,
            experience.stakeholders, experience.learned,
        ])).lower()

        if any(word.lower() in haystack for word in words):
            found.append({"kind": "experience", "id": experience.id,
                          "title": experience.title})

    for project in db.query(models.Project).all():
        haystack = " ".join(filter(None, [
            project.name, project.description, project.results,
        ])).lower()

        if any(word.lower() in haystack for word in words):
            found.append({"kind": "project", "id": project.id,
                          "title": project.name})

    return found[:3]


def build(db, opportunity) -> dict:
    """이 공고에서 강조할 것."""
    text = opportunity.description or ""

    if not text.strip():
        return {
            "has_text": False,
            "note": "공고 본문이 없어요. 원문을 붙여 넣으면 무엇을 강조할지 뽑아 드려요.",
            "sections": [], "traits": [], "flags": [],
        }

    rows = []

    for row in traits(text):
        words = next(item[2] for item in TRAITS if item[0] == row["key"])
        mine = _my_evidence(db, words)

        rows.append({
            **row,
            "mine": mine,
            # 쓸 거리가 없으면 없다고 한다. 그게 다음에 만들 것이다.
            "standing": "ready" if mine else "nothing",
        })

    return {
        "has_text": True,
        "note": "",
        "sections": sections(text),
        "traits": rows,
        # 학력 · 경력 같은 걸림돌은 따로 보인다. 강조할 것이 아니라
        # 지원 전에 확인할 것이다.
        "flags": posting_parser.find_requirement_flags(text),
    }
