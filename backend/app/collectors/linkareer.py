"""링커리어 인턴 목록 수집원 — 신입에게 가장 부족한 인턴 공고.

지금 소스(고용24 공채속보 · 기업 채용 보드 · 카카오)는 구조적으로 정규직 위주다.
2026-09-21 기준 들인 52건 중 인턴은 7건뿐이었다.

약관과 robots 를 먼저 봤다.
  - robots.txt 는 목록 · 공고를 허용한다 (막힌 것은 STEM 학습 경로뿐)
  - 이용약관 제16조는 "자동 접속 프로그램 등으로 **서버에 부하를 일으켜 정상적인 서비스를
    방해하는** 행위" 를 금지한다. 제20조의 크롤링 금지는 **STEM 서비스** 에 걸려 있다.

그래서 부하를 만들지 않는 선을 코드로 박는다.
  - **하루 한 번, 목록 한 쪽**(기본). 공고마다 상세를 따로 열지 않는다 —
    목록 페이지에 제목 · 회사 · 마감이 이미 들어 있다.
  - CareerOS/1.0 으로 정체를 밝히고, robots 를 매번 먼저 확인한다
  - 막히면 조용히 0건이 되지 않고 수집 실패로 남는다 (collector_runs)

본문은 가져오지 않는다. 관심 가는 공고는 사람이 열어서 "주소로 가져오기" 로 본문을 넣는다.
"""

import json
import os
import re
from datetime import datetime

from .. import auth
from ..services import job_fit
from ..services.url_import import USER_AGENT, ImportError_, _open, robots_allows
from . import base


SOURCE_NAME = "linkareer"

LIST_URL = "https://linkareer.com/list/intern"
DETAIL_URL = "https://linkareer.com/activity"

NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

# 한 쪽에 20~24건. 하루 한 번 세 쪽(≈64건)까지만 본다 — 그 이상은 부하다.
DEFAULT_MAX_PAGES = 3


def max_pages() -> int:
    try:
        return max(1, min(3, int(os.getenv("CAREER_OS_LINKAREER_MAX_PAGES", DEFAULT_MAX_PAGES))))
    except ValueError:
        return DEFAULT_MAX_PAGES


def is_available() -> bool:
    return os.getenv("CAREER_OS_LINKAREER", "1") == "1" and not auth.is_public_demo()


def _deadline(value):
    """recruitCloseAt 은 밀리초 타임스탬프. 없으면 비운다 — 상시 모집이 많다."""
    try:
        return datetime.fromtimestamp(int(value) / 1000)
    except (TypeError, ValueError, OSError):
        return None


def _activities(html: str) -> list[dict]:
    """목록 페이지에 박혀 있는 데이터에서 공고만 꺼낸다."""
    found = NEXT_DATA.search(html or "")

    if not found:
        raise base.CollectorError(
            "링커리어 목록에서 공고 데이터를 찾지 못했어요. 화면 구조가 바뀐 것 같아요."
        )

    try:
        data = json.loads(found.group(1))
    except json.JSONDecodeError as error:
        raise base.CollectorError("링커리어 목록을 읽지 못했어요.") from error

    rows = []
    stack = [data]

    while stack:
        node = stack.pop()

        if isinstance(node, dict):
            if node.get("__typename") == "Activity" and node.get("title"):
                rows.append(node)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)

    return rows


def fetch(opener=None) -> list[dict]:
    opener = opener or _open

    if not robots_allows(LIST_URL, opener):
        raise base.CollectorError(
            "링커리어가 robots.txt 로 자동 접근을 막았어요. 수집을 멈춥니다 — "
            "관심 공고는 주소로 가져오기로 넣으세요."
        )

    kept = []
    seen = set()

    for page in range(1, max_pages() + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"

        try:
            html = opener(url)
        except ImportError_ as error:
            raise base.CollectorError(f"링커리어 목록을 열지 못했어요 — {error}") from error

        for activity in _activities(html):
            identifier = str(activity.get("id") or "")

            if not identifier or identifier in seen:
                continue
            seen.add(identifier)

            title = (activity.get("title") or "").strip()

            # 본문이 없으므로 제목만으로 판단한다. 데이터 · AI 가 제목에 없으면 넘긴다.
            ok, why = job_fit.judge_section(title, job_fit.career_from_title(title))
            if not ok:
                continue

            kept.append({
                "id": identifier,
                "title": title,
                "company": (activity.get("organizationName") or "").strip(),
                "deadline": _deadline(activity.get("recruitCloseAt")),
                "job_types": activity.get("jobTypes") or [],
                "why": why,
            })

    return kept


def normalize(raw: dict) -> dict:
    lines = [
        f"맞는 이유: {raw.get('why', '')}",
        "",
        "본문은 가져오지 않았어요. 공고를 열어 보고 넣을 만하면 "
        "기회 → 붙여넣기 → '주소로 가져오기' 로 본문을 채우세요.",
        "",
        "출처: 링커리어 인턴 목록",
    ]

    return base.normalize_opportunity(
        source=SOURCE_NAME,
        external_id=str(raw.get("id") or ""),
        title=raw.get("title", ""),
        organization=raw.get("company", ""),
        description="\n".join(lines),
        url=f"{DETAIL_URL}/{raw['id']}" if raw.get("id") else "",
        employment_type="인턴",
        deadline=raw.get("deadline"),
        raw_payload="",
    )
