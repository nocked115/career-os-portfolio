"""고용24 공채속보 수집원.

공식 Open API 다 (https://www.work24.go.kr — OPEN-API). 스크래핑하지 않는다.
개인회원 인증키로는 채용정보 목록 · 상세가 막혀 있고, **공채속보** · 공채기업정보 ·
채용행사만 열린다 (2026-09-16 고용24 안내). 여기서는 공채속보만 쓴다.

    목록  callOpenApiSvcInfo210L21  제목 · 기업 · 접수 기간 · 고용형태 · 원문 링크
    상세  callOpenApiSvcInfo210D21  + 모집 부문별 직무 설명 · 신입/경력 · 근무지 · 전형 단계

**목록 제목만으로는 직무를 알 수 없다.** 실제로 264건 중 제목에 데이터 · AI 가 들어간 것은
1건뿐이었고, "대졸 신입사원 모집" 안에 데이터 직무가 있다. 그래서 상세의 모집 부문으로 고른다.

약관과 지킬 것
- 공공저작물 제4유형: 출처 표시, 상업적 이용 금지, 변경 금지 → source="work24" 로 저장하고
  화면이 "고용24" 를 붙인다. 공개 데모에서는 켜지 않는다.
- 인증키를 공개하지 않는다. .env 에만 둔다. 오류 메시지에 URL 을 넣지 않는다.
- 응답에 없는 것은 지어내지 않는다. 설명은 받은 부문 · 직무 · 전형 이름을 이어 붙일 뿐이다.
"""

import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .. import auth
from ..services import job_fit
from . import base


SOURCE_NAME = "work24"

LIST_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L21.do"
DETAIL_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210D21.do"

PAGE_SIZE = 100          # 목록 한 번에 받는 최대치 (실측)
MAX_PAGES = 10

# 하루 한 번 도는 수집에서 상세를 몇 건까지 부를지. 2026-09-16 에 접수 중인 공채가 264건이었다.
DEFAULT_MAX_DETAILS = 300

# 무엇을 들일지는 services/job_fit.py 가 모집 부문마다 판단한다.
#
# 처음에는 "데이터" · "AI" 를 직무 설명 어디서든 찾았고(35건 중 절반이 인사 · 영업), 다음에는
# 말을 두 층으로 나눴다. 그래도 요즘 직무 설명에 흔한 "데이터 분석 기반 …" 한 줄 때문에
# 2026-09-17 들인 18건 중 10건이 영업 · 마케팅 · 생산이었다. 이제 부문 이름과 하는 일을 같이 본다.


def _key() -> str:
    return os.getenv("WORK24_API_KEY", "").strip()


def max_details() -> int:
    try:
        return max(0, int(os.getenv("CAREER_OS_WORK24_MAX_DETAILS", DEFAULT_MAX_DETAILS)))
    except ValueError:
        return DEFAULT_MAX_DETAILS


def is_available() -> bool:
    """키가 있고, 공개 데모가 아닐 때만. 공개 데모에 싣는 것은 비영리 · 변경 금지 조건에 걸린다."""
    return bool(_key()) and not auth.is_public_demo()


def _get_xml(url: str, params: dict) -> ET.Element:
    query = urllib.parse.urlencode({"authKey": _key(), "returnType": "XML", **params})
    request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "career-os"})

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        raise base.CollectorError(f"고용24 HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError) as error:
        # 오류 메시지에 URL 이 들어가면 키가 로그에 남는다. 종류만 남긴다.
        raise base.CollectorError(
            f"고용24에 연결하지 못했습니다 ({type(error).__name__})"
        ) from None

    try:
        return ET.fromstring(raw.strip())
    except ET.ParseError:
        raise base.CollectorError("고용24 응답을 읽지 못했습니다 (XML 아님)") from None


def _text(node, tag: str) -> str:
    return re.sub(r"\s+", " ", (node.findtext(tag) or "")).strip()


def _matches(text: str, words: list[str]) -> list[str]:
    """채용 행사 수집(work24_events)이 행사 이름 · 지역을 고를 때 쓴다."""
    found = []
    lowered = text.lower()
    for word in words:
        if re.fullmatch(r"[A-Za-z]+", word):
            if re.search(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", text, re.IGNORECASE):
                found.append(word)
        elif word.lower() in lowered:
            found.append(word)
    return found


def _detail(seqno: str) -> dict:
    root = _get_xml(DETAIL_URL, {"callTp": "D", "empSeqno": seqno})

    sections = []
    for info in root.findall(".//empRecrList/empRecrListInfo"):
        sections.append({
            "name": _text(info, "empRecrNm"),
            "job": _text(info, "jobCont"),
            "career": _text(info, "empWantedCareerNm"),
            "education": _text(info, "empWantedEduNm"),
            "region": _text(info, "workRegionNm"),
        })

    steps = [
        _text(info, "selsNm")
        for info in root.findall(".//empSelsList/empSelsListInfo")
        if _text(info, "selsNm")
    ]

    return {
        "sections": sections,
        "steps": steps,
        "homepage": _text(root, "empWantedHomepg"),
        "company_type": _text(root, "coClcdNm"),
    }


def fetch() -> list[dict]:
    """공채속보 목록 → 상세 → 키워드가 부문 · 직무 · 제목에 있는 것만."""
    # 키가 없으면 요청을 보내지 않는다. "키 없음" 응답을 받는 한 번도 외부 호출이다.
    if not _key():
        raise base.CollectorError("고용24 인증키(WORK24_API_KEY)가 없습니다")

    postings = []
    for page in range(1, MAX_PAGES + 1):
        root = _get_xml(LIST_URL, {"callTp": "L", "startPage": page, "display": PAGE_SIZE})
        items = root.findall(".//dhsOpenEmpInfo")
        for item in items:
            postings.append({
                "seqno": _text(item, "empSeqno"),
                "title": _text(item, "empWantedTitle"),
                "company": _text(item, "empBusiNm"),
                "company_type": _text(item, "coClcdNm"),
                "start": _text(item, "empWantedStdt"),
                "end": _text(item, "empWantedEndt"),
                "employment_type": _text(item, "empWantedTypeNm"),
                "url": _text(item, "empWantedHomepgDetail") or _text(item, "empWantedMobileUrl"),
            })
        total = int(root.findtext("total") or 0)
        if not items or len(postings) >= total:
            break

    kept = []

    for posting in postings[: max_details()]:
        if not posting["seqno"]:
            continue
        try:
            detail = _detail(posting["seqno"])
        except base.CollectorError:
            # 상세 하나가 실패해도 나머지는 계속 본다.
            continue

        # 모집 부문마다 데이터 · AI 직무인지 본다 (services/job_fit.py).
        # 전에는 설명 어딘가에 "데이터 분석" 한 번만 있어도 들였다 — 건강식품 온라인 영업,
        # 홈쇼핑 MD 까지 들어왔다.
        judged = job_fit.judge_sections(detail["sections"])
        if not judged["fits"]:
            continue

        kept.append({
            **posting,
            **detail,
            "sections": [
                {key: value for key, value in section.items() if key != "why"}
                for section in judged["kept"]
            ],
            "dropped_sections": [section["name"] for section in judged["dropped"]],
            "matched": [section["why"] for section in judged["kept"]],
            "company_type": posting["company_type"] or detail["company_type"],
        })

    return kept


def _dash_date(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}" if re.fullmatch(r"\d{8}", value or "") else value


def normalize(raw: dict) -> dict:
    lines = []
    for section in raw.get("sections", []):
        head = " · ".join(part for part in (section["name"], section["career"], section["region"]) if part)
        lines.append(f"모집 부문: {head}" + (f" — {section['job']}" if section["job"] else ""))
        if section["education"]:
            lines.append(f"  학력: {section['education']}")

    if raw.get("steps"):
        lines.append("전형: " + " → ".join(raw["steps"]))
    if raw.get("start") or raw.get("end"):
        lines.append(f"접수: {_dash_date(raw.get('start', ''))} ~ {_dash_date(raw.get('end', ''))}")
    if raw.get("company_type"):
        lines.append(f"기업 구분: {raw['company_type']}")
    dropped = raw.get("dropped_sections", [])
    if dropped:
        # 데이터 · AI 가 아닌 부문은 설명에 넣지 않는다 — 스킬이 그 부문 설명에서 잘못 뽑힌다.
        lines.append(f"그 외 모집 부문 {len(dropped)}개({', '.join(dropped[:5])}) 는 데이터 · AI 직무가 아니라 뺐어요.")
    lines.append("출처: 고용24 공채속보")

    regions = []
    for section in raw.get("sections", []):
        if section["region"] and section["region"] not in regions:
            regions.append(section["region"])

    return base.normalize_opportunity(
        source=SOURCE_NAME,
        external_id=raw.get("seqno"),
        title=raw.get("title", ""),
        organization=raw.get("company", ""),
        # 여러 부문을 뽑는 공채에서 내게 맞는 부문. 목록에서 제목만으로는 모른다.
        role=" · ".join(section["name"] for section in raw.get("sections", []))[:200],
        description="\n".join(lines),
        url=raw.get("url") or raw.get("homepage", ""),
        location=", ".join(regions),
        employment_type=raw.get("employment_type", ""),
        deadline=raw.get("end") or None,
        raw_payload="",
    )
