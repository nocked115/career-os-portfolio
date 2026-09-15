"""고용24 채용행사 수집원 — 취업박람회 · 채용설명회.

공식 Open API (고용24 OPEN-API, 개인회원에게 열린 채용행사). 스크래핑하지 않는다.

    목록  callOpenApiSvcInfo210L11  지역 · 행사번호 · 행사명 · 기간 · 시작일
    상세  callOpenApiSvcInfo210D11  (eventNo + areaCd) 일시 · 장소 · 내용 · 담당자 연락처

2026-09-16 에 전체 1,854건 중 앞으로 열리는 행사는 37건, 서울 · 경기 · 인천은 16건이었다.
그 대부분이 조리사 · 어린이집 · 호텔 현장면접이라 **이름으로 고른다** — 박람회 · 청년 · IT · 데이터 같은
말이 있는 행사만, 기업이 참가 신청하는 공고는 뺀다.

지킬 것
- 상세에 담당자 이름 · 전화 · 팩스 · 이메일이 온다. **저장하지 않는다.** 일시 · 장소 · 내용만 옮긴다.
- 원문 링크가 응답에 없다. 주소를 지어내지 않고 비워 둔다.
- 출처 표시(고용24), 공개 데모에서는 켜지 않는다, 오류에 인증키를 남기지 않는다.
"""

import os
import re
from datetime import date

from . import base
from . import work24


SOURCE_NAME = "work24_event"

LIST_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L11.do"
DETAIL_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210D11.do"

PAGE_SIZE = 100
MAX_PAGES = 30                 # 1,854건 → 19쪽 (실측)
MAX_CONTENT = 600

DEFAULT_REGIONS = "서울,경기,인천"
DEFAULT_WORDS = "박람회,잡페스타,채용설명회,청년,대학,IT,데이터,AI,디지털,전산,SW,소프트웨어,개발"
DEFAULT_EXCLUDE = "참가 기업,참가기업,참여기업,참여 기업,기업 모집,구인기업"


def _words(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [word.strip() for word in raw.split(",") if word.strip()]


def is_available() -> bool:
    return work24.is_available()


def _upcoming(item: dict, today: date) -> bool:
    end = _period(item.get("term", ""))[1] or item.get("start", "")
    return bool(end) and end >= today.isoformat()


def _period(term: str):
    """'2026-10-16 ~ 2026-10-16 (10:00 ~ 17:00)' → ('2026-10-16', '2026-10-16')."""
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", term or "")
    if not dates:
        return None, None
    return dates[0], dates[-1]


def _wanted(item: dict) -> list[str]:
    name = item.get("name", "")
    if work24._matches(name, _words("CAREER_OS_WORK24_EVENT_EXCLUDE", DEFAULT_EXCLUDE)):
        return []
    if not any(region in item.get("area", "") for region in _words("CAREER_OS_WORK24_EVENT_REGIONS", DEFAULT_REGIONS)):
        return []
    return work24._matches(name, _words("CAREER_OS_WORK24_EVENT_WORDS", DEFAULT_WORDS))


def fetch() -> list[dict]:
    if not work24._key():
        raise base.CollectorError("고용24 인증키(WORK24_API_KEY)가 없습니다")

    today = date.today()
    events = []

    for page in range(1, MAX_PAGES + 1):
        root = work24._get_xml(LIST_URL, {"callTp": "L", "startPage": page, "display": PAGE_SIZE})
        items = root.findall(".//empEvent")
        for node in items:
            events.append({
                "no": work24._text(node, "eventNo"),
                "area_code": work24._text(node, "areaCd"),
                "area": work24._text(node, "area"),
                "name": work24._text(node, "eventNm"),
                "term": work24._text(node, "eventTerm"),
                "start": work24._text(node, "startDt"),
            })
        total = int(root.findtext("total") or 0)
        if not items or len(events) >= total:
            break

    kept = []
    for event in events:
        if not event["no"] or not _upcoming(event, today):
            continue
        matched = _wanted(event)
        if not matched:
            continue

        try:
            detail = work24._get_xml(
                DETAIL_URL, {"callTp": "D", "eventNo": event["no"], "areaCd": event["area_code"]}
            )
            event = {
                **event,
                # 담당자 · 연락처(charger · inqTelNo · fax · email)는 읽지도 옮기지도 않는다.
                "term": work24._text(detail, "eventTerm") or event["term"],
                "place": work24._text(detail, "eventPlc"),
                "content": work24._text(detail, "subMatter")[:MAX_CONTENT],
            }
        except base.CollectorError:
            pass

        kept.append({**event, "matched": matched})

    return kept


def normalize(raw: dict) -> dict:
    start, end = _period(raw.get("term", ""))
    lines = [
        f"일시: {raw['term']}" if raw.get("term") else "",
        f"장소: {raw['place']}" if raw.get("place") else "",
        f"지역: {raw['area']}" if raw.get("area") else "",
        f"내용: {raw['content']}" if raw.get("content") else "",
        f"찾은 말: {', '.join(raw.get('matched', []))}",
        "출처: 고용24 채용행사 (원문 링크 없음 — 고용24에서 행사명으로 찾아 주세요)",
    ]

    return base.normalize_opportunity(
        source=SOURCE_NAME,
        external_id=raw.get("no"),
        opportunity_type="job_event",
        title=raw.get("name", ""),
        organization="",
        description="\n".join(line for line in lines if line),
        url="",
        location=raw.get("place") or raw.get("area", ""),
        employment_type="",
        deadline=end or raw.get("start") or None,
        raw_payload="",
    )
