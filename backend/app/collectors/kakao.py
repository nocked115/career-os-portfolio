"""카카오 채용 목록 수집원 — 카카오 채용 사이트가 자기 화면에 쓰는 공개 주소.

Greenhouse 처럼 문서로 공개된 API 는 아니다. 카카오 채용 페이지가 로그인 없이 부르는
`/public/api/job-list` 이고, 2026-09-21 기준 robots.txt 가 없어 막는 규칙도 없다.
그래서 **출처별 허용 방식**(DECISIONS 39장)의 ② 허용된 공개 소스로 둔다.

문서화된 API 가 아니라는 위험을 이렇게 다룬다.
  - 하루 한 번, 목록 몇 쪽만. 상세는 부르지 않는다 (목록 응답에 본문이 들어 있다)
  - CareerOS/1.0 으로 정체를 밝힌다. 브라우저인 척하지 않는다
  - robots.txt 가 생기면 그때부터 따른다 — 매번 먼저 확인한다
  - 막히면(403 · 429 · 주소 변경) **조용히 0건이 되지 않는다.** 수집이 실패로 남아
    화면에 "막혔다" 고 뜬다. 공고가 없는 건지 수집기가 깨진 건지 모르는 게 가장 나쁘다.

네이버는 목록 요청이 "접근권한이 없습니다" 로 막혔고, 토스는 robots 가 채용 목록을
막아 두었다. 둘은 붙이지 않는다. 라인은 목록이 화면을 그려야 보여 주소로 한 건씩 가져온다.
"""

import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .. import auth
from ..services import job_fit
from ..services.url_import import USER_AGENT, robots_allows, to_text
from . import base


SOURCE_NAME = "kakao"

LIST_URL = "https://careers.kakao.com/public/api/job-list"
DETAIL_URL = "https://careers.kakao.com/jobs"

# 기술 직군만. 카카오 채용 화면의 구분을 그대로 쓴다.
DEFAULT_PART = "TECHNOLOGY"

# 하루 한 번 도는 수집에서 목록을 몇 쪽까지 볼지. 2026-09-21 기준 기술 직군이 3쪽(32건)이었다.
DEFAULT_MAX_PAGES = 5

MAX_BODY = 4000


def part() -> str:
    return os.getenv("CAREER_OS_KAKAO_PART", DEFAULT_PART).strip()


def max_pages() -> int:
    try:
        return max(1, int(os.getenv("CAREER_OS_KAKAO_MAX_PAGES", DEFAULT_MAX_PAGES)))
    except ValueError:
        return DEFAULT_MAX_PAGES


def is_available() -> bool:
    """켜고 끄는 스위치. 공개 데모에서는 켜지 않는다."""
    return os.getenv("CAREER_OS_KAKAO", "1") == "1" and not auth.is_public_demo()


def _get_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        # 막힌 것을 성공으로 넘기지 않는다. 수집 결과에 실패로 남는다.
        raise base.CollectorError(
            f"카카오 채용 목록이 {error.code} 로 답했어요. 주소가 바뀌었거나 막힌 것 같아요 — "
            "관심 공고는 주소로 가져오기 · 붙여넣기로 넣으세요."
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise base.CollectorError("카카오 채용 목록에 연결하지 못했어요") from error
    except json.JSONDecodeError as error:
        raise base.CollectorError(
            "카카오 채용 목록이 글이 아닌 것을 돌려줬어요. 주소가 바뀐 것 같아요."
        ) from error


def _page_url(page: int) -> str:
    query = urllib.parse.urlencode({
        "skillSet": "",
        "part": part(),
        "company": "ALL",
        "keyword": "",
        "employeeType": "",
        "page": page,
    })
    return f"{LIST_URL}?{query}"


def _body_of(job: dict) -> str:
    parts = [job.get(key) or "" for key in ("introduction", "workContentDesc", "qualification")]
    return to_text(html.unescape("\n".join(parts)))[:MAX_BODY]


def fetch() -> list[dict]:
    if not robots_allows(_page_url(1)):
        raise base.CollectorError(
            "카카오가 robots.txt 로 자동 접근을 막았어요. 수집을 멈춥니다 — "
            "관심 공고는 주소로 가져오기로 넣으세요."
        )

    kept = []
    page = 1
    total_pages = 1

    while page <= min(total_pages, max_pages()):
        data = _get_json(_page_url(page))
        total_pages = int(data.get("totalPage") or 1)

        for job in data.get("jobList") or []:
            title = (job.get("jobOfferTitle") or "").strip()
            body = _body_of(job)

            # 제목의 "(경력)" 을 읽는다. 신입이 지원할 수 없는 자리는 수요에 세지 않는다.
            career = job_fit.career_from_title(title)

            ok, why = job_fit.judge_section(title, career, body, weak_ok=False, min_strong=2)
            if not ok:
                continue

            kept.append({
                "id": job.get("realId") or "",
                "title": title,
                "company": (job.get("companyName") or "카카오").strip(),
                "location": (job.get("locationName") or "").strip(),
                "employment_type": (job.get("employeeTypeName") or "").strip(),
                "skills": [s.get("name", "") for s in job.get("skillSetList") or []],
                "career": career,
                "deadline": job.get("endDate"),
                "body": body,
                "why": why,
            })

        page += 1

    return kept


def normalize(raw: dict) -> dict:
    lines = []

    if raw.get("career"):
        lines.append(f"경력 조건(제목 기준): {raw['career']}")
    if raw.get("skills"):
        lines.append("쓰는 기술: " + " · ".join(part for part in raw["skills"] if part))
    lines.append(f"맞는 이유: {raw.get('why', '')}")
    lines.append("")
    lines.append(raw.get("body", ""))
    lines.append("")
    lines.append("출처: 카카오 채용")

    return base.normalize_opportunity(
        source=SOURCE_NAME,
        external_id=str(raw.get("id") or ""),
        title=raw.get("title", ""),
        organization=raw.get("company", ""),
        description="\n".join(lines),
        url=f"{DETAIL_URL}/{raw['id']}" if raw.get("id") else "",
        location=raw.get("location", ""),
        employment_type=raw.get("employment_type", ""),
        deadline=raw.get("deadline") or None,
        raw_payload="",
    )
