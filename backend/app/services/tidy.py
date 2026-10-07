"""쌓인 공고를 치운다 — 중복 묶기와 마감 내리기.

수집원이 다섯이라 같은 공고가 여러 번 들어온다. 실제로 SK인텔릭스
데이터 분석 인턴 하나가 #116 · #118 · #127 · #132 **네 줄**이었다.
한 회사가 요구하는 스킬이 네 배로 세어지면 수요 비율이 통째로 틀어진다.

**지원서가 걸린 공고는 건드리지 않는다.** 2026-10-06 에 중복을 손으로
치우다 #118 을 보관함으로 내렸는데, 거기 '관심 있음' 지원서(#3)가
달려 있었다. 화면에서 그 지원서가 어느 공고인지 안 보이게 됐다.
자동으로 돌릴 것이라면 이 선이 가장 중요하다.

원문을 다시 받아오지 않는다. 공고의 70%가 url 이 비어 있어서 "들어가
보고 판단" 이 대부분 불가능하고, 되는 것도 사이트마다 마감 표시가
달라 규칙으로 읽을 수 없다. **이미 저장된 마감일**로만 판단한다 —
그게 틀렸으면 원문이 아니라 수집기를 고쳐야 한다.
"""

import re
from datetime import date, datetime

from .. import models


# 묶을 때 무시할 것 — 같은 공고를 수집원마다 다르게 적는다.
#   "[SK인텔릭스] 데이터 분석 인턴 채용" · "SK인텔릭스｜데이터 분석 인턴 채용"
#   "데이터 분석 인턴" · "데이터 분석 인턴 채용"
# 괄호 **안을 통째로** 지우면 안 된다. 카카오 "LLM Research Engineer
# (Pre-training)" 과 "(Post-training)" 이 같은 줄이 되어 하나가 잘못
# 보관됐다. 괄호는 기호로만 떼고(_PUNCT), 안에 든 말은 키에 남긴다.
# 대신 어느 공고에나 붙는 **군더더기 낱말**만 지운다.
_NOISE = re.compile(
    r"채용\s*공고|채용\s*안내|모집\s*공고|채용|모집|공고"
    r"|신입\s*/?\s*경력|신입|경력|정규직|계약직"
    r"|마감\s*임박|상시|수시|추가\s*모집"
)
# 전각 기호까지 넣는다 — "SK인텔릭스｜데이터 분석 인턴" 의 ｜ 가 U+FF5C 다.
_PUNCT = re.compile(
    r"[\s·ㅣ|｜/／,，.。\-－_~〜「」『』【】\[\]()（）＜＞<>:：;；]+"
)


def _key(text: str) -> str:
    """같은 것을 다르게 적은 걸 같게 본다."""
    cleaned = _NOISE.sub(" ", text or "")
    return _PUNCT.sub("", cleaned).lower()


def _org_key(opportunity) -> str:
    """회사 이름. '에스케이인텔릭스' 와 'SK인텔릭스' 는 못 묶는다 —
    한글 음차까지 맞추려면 사전이 필요하고, 틀리게 묶는 쪽이 더 나쁘다."""
    return _key(opportunity.organization or "")


def _richness(opportunity) -> tuple:
    """어느 줄을 남길까. 설명이 길고 스킬이 많이 붙은 것이 원본에 가깝다.
    사람이 직접 넣은 것(manual)을 수집된 것보다 먼저 둔다."""
    return (
        opportunity.source == "manual",
        len(opportunity.skills or []),
        len(opportunity.description or ""),
        -opportunity.id,
    )


def find_duplicates(db) -> list[dict]:
    """같은 (회사, 제목)으로 보이는 묶음. 저장하지 않는다."""
    groups: dict[tuple, list] = {}

    for opportunity in db.query(models.Opportunity).all():
        if opportunity.status in ("archived", "closed"):
            continue

        org = _org_key(opportunity)
        title = _key(opportunity.title or "")

        # 제목 앞에 회사 이름이 붙어 오는 수집원이 있다
        # ("SK인텔릭스｜데이터 분석 인턴 채용"). 어차피 회사로 묶으니 떼어낸다.
        if org and title.startswith(org):
            title = title[len(org):]

        if not title:
            continue

        groups.setdefault((org, title), []).append(opportunity)

    found = []

    for (org, title), rows in groups.items():
        if len(rows) < 2:
            continue

        rows.sort(key=_richness, reverse=True)
        keep, rest = rows[0], rows[1:]

        # 지원서가 걸린 줄은 남긴다. 치우면 그 지원서가 어느 공고인지
        # 화면에서 사라진다 — 실제로 한 번 그렇게 깨뜨렸다.
        protected = [row for row in rest if row.applications]
        droppable = [row for row in rest if not row.applications]

        if not droppable:
            continue

        found.append({
            "organization": keep.organization or "",
            "title": keep.title,
            "keep": {"id": keep.id, "source": keep.source},
            "drop": [{"id": row.id, "source": row.source} for row in droppable],
            "kept_for_applications": [row.id for row in protected],
        })

    found.sort(key=lambda item: -len(item["drop"]))

    return found


# 서울의 25개 구. 행사가 서울인지 가리는 데 쓴다.
SEOUL_GU = (
    "종로", "중구", "용산", "성동", "광진", "동대문", "중랑", "성북", "강북",
    "도봉", "노원", "은평", "서대문", "마포", "양천", "강서", "구로", "금천",
    "영등포", "동작", "관악", "서초", "강남", "송파", "강동",
)

SEOUL = re.compile(r"서울|" + "|".join(gu + r"구?" for gu in SEOUL_GU))

FAR_REASON = "서울 밖 채용 행사 — 갈 수 없어요"


def find_far_events(db) -> list[dict]:
    """서울 밖 채용 행사.

    수현: "박람회 같은 것도 서울 이외의 지역은 좀 지워줄래? 어차피 못 가는데."

    **행사만** 본다. 공고는 지역이 멀어도 지원할 수 있지만(원격 · 이사 ·
    지사 배치), 박람회는 그날 그 자리에 가야 하는 것이라 못 가면 끝이다.

    서울이라는 표시가 **있을 때만** 남긴다. 지역을 못 읽으면 치운다 —
    못 가는 행사를 남겨두는 비용이, 갈 수 있는 행사를 하나 놓치는 비용보다
    작다. 지우지 않고 보관함으로 내리므로 되돌릴 수 있다.
    """
    rows = []

    for opportunity in db.query(models.Opportunity).all():
        if opportunity.opportunity_type != "job_event":
            continue

        if opportunity.status in ("archived", "closed"):
            continue

        if opportunity.applications:
            continue

        text = f"{opportunity.title or ''}\n{opportunity.location or ''}"

        if SEOUL.search(text):
            continue

        rows.append({
            "id": opportunity.id,
            "title": opportunity.title,
            "location": opportunity.location or "",
        })

    return rows


def find_expired(db, today: date | None = None) -> list[dict]:
    """마감일이 지났는데 아직 안 닫힌 것."""
    today = today or date.today()

    rows = []

    for opportunity in db.query(models.Opportunity).all():
        if opportunity.status in ("archived", "closed"):
            continue

        deadline = opportunity.deadline

        if deadline is None:
            continue

        if isinstance(deadline, datetime):
            deadline = deadline.date()

        if deadline >= today:
            continue

        rows.append({
            "id": opportunity.id,
            "title": opportunity.title,
            "organization": opportunity.organization or "",
            "deadline": deadline.isoformat(),
            "days_past": (today - deadline).days,
            # 지원한 공고도 닫는다 — 마감은 사실이다. 다만 지우지는 않는다.
            "has_application": bool(opportunity.applications),
        })

    rows.sort(key=lambda item: -item["days_past"])

    return rows


def preview(db, today: date | None = None) -> dict:
    """무엇을 치울지 보여주기만 한다."""
    duplicates = find_duplicates(db)
    expired = find_expired(db, today)
    far_events = find_far_events(db)

    return {
        "duplicates": duplicates,
        "expired": expired,
        "far_events": far_events,
        "will_archive": sum(len(item["drop"]) for item in duplicates) + len(far_events),
        "will_close": len(expired),
    }


def apply(db, today: date | None = None) -> dict:
    """실제로 치운다. 지우지 않고 상태만 바꾼다 — 되돌릴 수 있어야 한다."""
    plan = preview(db, today)

    for item in plan["duplicates"]:
        keep_title = item["title"]
        for row in item["drop"]:
            opportunity = db.get(models.Opportunity, row["id"])
            opportunity.status = "archived"
            # 치운 줄에 걸린 즐겨찾기는 같이 내린다. 안 내리면 화면에
            # 보관함에 있는 공고가 즐겨찾기로 계속 떠 있다 — 실제로 그랬다.
            opportunity.favorite = False
            # **어느 줄로 묶였는지** 적는다. 그냥 "중복" 이라고만 하면
            # 잘못 묶였을 때 알아볼 수가 없다. 실제로 카카오
            # "(Pre-training)" 이 "(Post-training)" 으로 잘못 묶였는데
            # 까닭이 없어서 버그인 걸 한참 뒤에야 알았다(커밋 138).
            opportunity.tidied_reason = f"'{keep_title}' 과 같은 공고로 묶음"

    for row in plan["far_events"]:
        opportunity = db.get(models.Opportunity, row["id"])
        opportunity.status = "archived"
        opportunity.favorite = False
        # 왜 치웠는지 남긴다 — 나중에 "이게 왜 없지" 를 묻지 않게.
        if not opportunity.blocked_reason:
            opportunity.blocked_reason = FAR_REASON
        opportunity.tidied_reason = FAR_REASON

    for row in plan["expired"]:
        opportunity = db.get(models.Opportunity, row["id"])
        opportunity.status = "closed"
        # 마감이 지난 공고를 "잊지 않게" 띄워 둘 이유가 없다.
        opportunity.favorite = False
        opportunity.tidied_reason = (
            f"마감 지남 — {opportunity.deadline:%Y-%m-%d}"
            if opportunity.deadline else "마감 지남"
        )

    db.commit()

    return plan
