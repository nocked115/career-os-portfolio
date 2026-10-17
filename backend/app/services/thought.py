"""적어 둔 생각 — 그리고 앱이 아는 것 중 그 생각에 닿는 것.

수현: "요즘 생각 고민이나 이런 거, 대학원을 갈지 말지 고민하는 거
얘는 모르잖아."

적어 두는 것만으로는 메모장과 다르지 않다. 이 앱이 더할 수 있는 건
**이미 가진 데이터를 그 질문 옆에 놓는 것**이다. "대학원을 갈지 말지"
는 느낌으로 정할 일이 아니다 — 석박사 요건에 막힌 공고가 몇 건인지,
그게 어느 스킬에 쏠려 있는지가 이미 앱 안에 있다.

그래서 고민마다 닿는 근거를 붙인다. **지어내지 않는다** — 닿는 것이
없으면 없다고 한다.
"""
import re
from datetime import datetime

from .. import models


KINDS = ("question", "idea", "note")

KIND_LABELS = {
    "question": "아직 못 정한 것",
    "idea": "해 볼 만한 것",
    "note": "적어 둔 것",
}

# 대학원 고민에 닿는 근거는 앱이 이미 들고 있다 — 자격 때문에 막힌 공고.
GRAD_SCHOOL = re.compile(r"대학원|석사|박사|진학|학위")


def serialize(thought, evidence=None) -> dict:
    opened_days = (datetime.now() - thought.created_at).days

    return {
        "id": thought.id,
        "kind": thought.kind,
        "kind_label": KIND_LABELS.get(thought.kind, thought.kind),
        "body": thought.body,
        "source": thought.source,
        "status": thought.status,
        "decision": thought.decision,
        "decided_at": thought.decided_at,
        "created_at": thought.created_at,
        # 며칠째 열려 있는가. 오래 열린 고민은 그 자체로 신호다.
        "open_days": opened_days if thought.status == "open" else None,
        "evidence": evidence,
    }


def evidence_for(db, thought) -> dict | None:
    """이 생각에 닿는, 앱이 이미 아는 것.

    지금은 한 가지만 본다 — 대학원 고민에는 자격 때문에 막힌 공고를
    붙인다. 규칙을 늘리기 전에 이 하나가 실제로 쓸모 있는지부터 본다.
    억지로 갖다 붙이면 근거가 아니라 장식이 된다.
    """
    if thought.kind != "question" or not GRAD_SCHOOL.search(thought.body or ""):
        return None

    from . import aspiration

    sheet = aspiration.build(db)

    if not sheet["postings"]:
        return None

    degree = next(
        (row for row in sheet["conditions"] if row["kind"] == "degree"), None
    )

    return {
        "label": "자격 때문에 지금 못 쓰는 공고",
        "postings": sheet["postings"],
        "organizations": sheet["organizations"][:3],
        "degree_lines": (degree or {}).get("lines", [])[:2],
        "top_skills": [row["skill"] for row in sheet["skills"][:5]],
        "where": "기회 화면의 '지금은 지원 못 하는 자리가 요구하는 것'",
    }


def create(db, kind: str, body: str, source: str = "") -> dict:
    thought = models.Thought(
        kind=kind if kind in KINDS else "note",
        body=body.strip(),
        source=(source or "").strip(),
    )
    db.add(thought)
    db.commit()
    db.refresh(thought)

    return serialize(thought, evidence_for(db, thought))


def decide(db, thought, decision: str) -> dict:
    """정했다고 표시한다. **무엇으로 정했는지 적는다.**

    비워서 보내면 다시 연다 — 잘못 닫는 일이 있고, 되돌릴 데가 없으면
    닫기를 망설이게 된다.
    """
    text = (decision or "").strip()

    if text:
        thought.status = "decided"
        thought.decision = text
        thought.decided_at = datetime.now()
    else:
        thought.status = "open"
        thought.decision = ""
        thought.decided_at = None

    db.commit()
    db.refresh(thought)

    return serialize(thought, evidence_for(db, thought))


def build_list(db, status: str | None = None) -> dict:
    query = db.query(models.Thought)

    if status:
        query = query.filter(models.Thought.status == status)

    rows = query.order_by(models.Thought.created_at.desc()).all()

    # 열린 고민을 맨 위로. 그게 아직 답해야 하는 것이다.
    rows.sort(key=lambda row: (
        row.status != "open",
        row.kind != "question",
    ))

    return {
        "thoughts": [serialize(row, evidence_for(db, row)) for row in rows],
        "open_questions": sum(
            1 for row in rows if row.status == "open" and row.kind == "question"
        ),
    }
