"""지금은 지원 못 하는 자리가 요구하는 것 — 목표표.

수현: "지원 자격이 안 되는 그거, 넣으면 좀 지우고 거기서 요구 역량만
뽑아서 참고자료로 쓰던가 해. 그럼 리스트로 나오잖아 — 해당 직무에
필요한 스킬들, 석사 박사/경험 이런 거랑 딥러닝 같은 거. 그리고 내가
가진 프로젝트나 이런 거랑 합치면 되겠네."

맞는 생각이다. **지원 못 하는 자리야말로 가고 싶은 자리다.** 석박사
요건에 걸린 KRAFTON Research 공고들이 매칭 점수 1·4·5위를 차지하고
있던 건 우연이 아니다 — 수현이 하려는 일에 가장 가까운 자리라서 점수가
높았고, 그래서 지금 지원할 수 없었다.

그 공고들을 목록에서 내리는 것까지는 이미 한다(blocked_reason). 내리고
나면 요구사항도 같이 사라지는 게 문제였다. 지금 못 가는 자리가 무엇을
요구하는지는 **몇 년짜리 목표표**이지 버릴 정보가 아니다.

여기서 세 가지를 합친다.

  조건   석박사 · 경력 연차 · 어학 — 시간이 풀어 주는 것과 아닌 것
  스킬   그 자리들이 공통으로 요구하는 도구
  증거   그 스킬을 이미 쓴 내 프로젝트

증거까지 붙이는 까닭은, 목록만 주면 "이만큼 모자라다" 로만 읽히기
때문이다. 같은 표에서 이미 가진 것이 함께 보여야 무엇을 더할지가 보인다.
"""
from collections import Counter

from .. import models
from . import posting_parser


# 시간이 지나면 풀리는 조건과 아닌 것을 가른다. 학력은 진학을 정해야
# 풀리고, 경력은 기다리면 쌓인다 — 같은 "막힘" 이 아니다.
CONDITION_ORDER = ("degree", "career", "language", "license")


def _blocked(db) -> list:
    """목표표에 올릴 막힌 공고.

    치우기가 서울 밖 채용 행사에도 blocked_reason 을 적는다(tidy.FAR_REASON).
    그건 "가고 싶은데 못 가는 자리" 가 아니라 그냥 안 가는 행사다. 섞으면
    목표표에 박람회 9건이 올라온다 — 실제로 그랬다.
    """
    from . import market, tidy

    return [
        row for row in (
            db.query(models.Opportunity)
            .filter(models.Opportunity.blocked_reason != "")
            .filter(models.Opportunity.filtered_reason == "")
            .filter(~models.Opportunity.opportunity_type.in_(market.DEMAND_OFF_TYPES))
            .all()
        )
        if row.blocked_reason != tidy.FAR_REASON
    ]


def build(db) -> dict:
    """막힌 공고에서 요구사항만 뽑아 한 장으로 돌려준다."""
    blocked = _blocked(db)

    if not blocked:
        return {
            "postings": 0,
            "organizations": [],
            "reasons": [],
            "conditions": [],
            "skills": [],
        }

    blocked_ids = {row.id for row in blocked}

    # --- 조건: 학력 · 경력 · 어학 · 자격증 ---
    found: dict[str, dict] = {}

    for row in blocked:
        for flag in posting_parser.find_requirement_flags(row.description or ""):
            entry = found.setdefault(
                flag["kind"],
                {"kind": flag["kind"], "label": flag["label"], "count": 0, "lines": []},
            )
            entry["count"] += 1
            # 원문 몇 줄만 남긴다. 다 모으면 공고를 다시 읽는 것과 같다.
            if flag["line"] not in entry["lines"] and len(entry["lines"]) < 3:
                entry["lines"].append(flag["line"])

    conditions = sorted(
        found.values(),
        key=lambda item: (
            CONDITION_ORDER.index(item["kind"])
            if item["kind"] in CONDITION_ORDER
            else len(CONDITION_ORDER)
        ),
    )

    # --- 스킬: 그 자리들이 요구하는 도구, 그리고 내 증거 ---
    skills = []

    for skill in db.query(models.Skill).all():
        linked = {row.id for row in skill.opportunities} & blocked_ids

        if not linked:
            continue

        # 이 스킬을 이미 쓴 내 프로젝트. "모자란 것" 만 보여 주지 않는다.
        projects = [
            {"id": project.id, "title": project.name, "status": project.status}
            for project in skill.projects
        ]

        level = skill.level or 0

        skills.append({
            "skill": skill.name,
            "skill_id": skill.id,
            "category": skill.category,
            "asked_by": len(linked),
            "my_level": level,
            "projects": projects,
            # 셋으로 가른다 — 쓴 적 있다 / 배우는 중 / 아직 없다.
            "standing": (
                "proven" if projects else "learning" if level > 0 else "missing"
            ),
        })

    # 많이 요구되는 것부터. 같으면 증거 없는 것을 위로 — 그게 할 일이다.
    skills.sort(key=lambda item: (-item["asked_by"], bool(item["projects"]), item["skill"]))

    return {
        "postings": len(blocked),
        "organizations": [
            name for name, _ in Counter(
                row.organization for row in blocked if row.organization
            ).most_common()
        ],
        "reasons": sorted({row.blocked_reason for row in blocked}),
        "conditions": conditions,
        "skills": skills,
    }
