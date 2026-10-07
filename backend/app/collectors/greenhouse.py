"""Greenhouse 채용 보드 수집원 — 기업이 공개한 공식 API.

사람인 API 는 반려됐고, 잡코리아 · 원티드는 공개 API 가 없다. 그런데 국내 IT 기업
상당수가 채용 페이지를 Greenhouse 로 돌리고, Greenhouse 는 **보드마다 공개 채용 API**
를 제공한다. 키도 승인도 필요 없다 — 기업이 스스로 공개한 자리다.

    https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true

2026-09-20 확인: 쿠팡 713 · 크래프톤 60 · 당근마켓 44 · 몰로코 44 · 센드버드 9.
본문(content)까지 와서 스킬 추출이 손으로 넣은 공고만큼 깊다.

거르는 순서는 셋이다. 전부 설명할 수 있어야 한다.
  1. 국내 근무지만        (쿠팡 713건 중 360건이 국내)
  2. 경력 중심 공고 제외   ("10년 이상" · Senior · Staff · Lead …) — 2027-02 졸업 예정 신입
  3. 데이터 · AI 직무만    services/job_fit 이 제목과 하는 일로 판단
"""

import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .. import auth
from ..services import job_fit
from ..services.url_import import to_text
from . import base


SOURCE_NAME = "greenhouse"

BOARDS_URL = "https://boards-api.greenhouse.io/v1/boards"

# 국내 데이터 · AI 신입을 뽑을 만한 곳. 환경변수로 바꾼다.
DEFAULT_BOARDS = "daangn,coupang,krafton,moloco,sendbird"

DEFAULT_REGION_WORDS = "seoul,korea,서울,대한민국,판교,pangyo"

# 본문을 통째로 저장하지 않는다 — 스킬을 찾기에 충분한 만큼만.
MAX_BODY = 4000


def _words(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [word.strip().lower() for word in raw.split(",") if word.strip()]


def boards() -> list[str]:
    return _words("CAREER_OS_GREENHOUSE_BOARDS", DEFAULT_BOARDS)


def region_words() -> list[str]:
    return _words("CAREER_OS_GREENHOUSE_REGIONS", DEFAULT_REGION_WORDS)


def is_available() -> bool:
    """키가 없어도 된다. 공개 데모에서는 켜지 않는다 — 수집은 실사용 배포의 일이다."""
    return bool(boards()) and not auth.is_public_demo()


def _get_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "CareerOS/1.0"})

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        raise base.CollectorError(f"Greenhouse 가 {error.code} 로 답했어요") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise base.CollectorError("Greenhouse 에 연결하지 못했어요") from error


def _in_korea(job: dict) -> bool:
    places = [(job.get("location") or {}).get("name", "")]
    places += [office.get("name", "") for office in job.get("offices") or []]
    joined = " ".join(places).lower()

    return any(word in joined for word in region_words())


def fetch() -> list[dict]:
    kept = []

    for board in boards():
        data = _get_json(f"{BOARDS_URL}/{urllib.parse.quote(board)}/jobs?content=true")

        for job in data.get("jobs", []):
            if not _in_korea(job):
                continue

            title = (job.get("title") or "").strip()
            body = to_text(html.unescape(job.get("content") or ""))[:MAX_BODY]
            career = job_fit.career_from_title(title)

            # weak_ok=False — 본문이 수천 자라 "AI" 가 한 번 스친 것으로는 안 된다.
            # 제목이 데이터 · AI 직무이거나, 하는 일에 직무를 특정하는 말이 있어야 한다.
            ok, why = job_fit.judge_section(title, career, body, weak_ok=False, min_strong=2)
            if not ok:
                continue

            kept.append({
                "board": board,
                "id": job.get("id"),
                "title": title,
                "company": (job.get("company_name") or board).strip(),
                "location": (job.get("location") or {}).get("name", ""),
                "departments": [d.get("name", "") for d in job.get("departments") or []],
                "url": job.get("absolute_url", ""),
                "deadline": job.get("application_deadline"),
                "body": body,
                "career": career,
                "why": why,
            })

    return kept


def normalize(raw: dict) -> dict:
    lines = []

    if raw.get("departments"):
        lines.append("부서: " + " · ".join(part for part in raw["departments"] if part))
    if raw.get("career"):
        lines.append(f"경력 조건(제목 기준): {raw['career']}")
    lines.append(f"맞는 이유: {raw.get('why', '')}")
    lines.append("")
    lines.append(raw.get("body", ""))
    lines.append("")
    lines.append("출처: 기업 채용 보드(Greenhouse 공개 API)")

    return base.normalize_opportunity(
        source=SOURCE_NAME,
        external_id=str(raw.get("id") or ""),
        title=raw.get("title", ""),
        organization=raw.get("company", ""),
        description="\n".join(lines),
        url=raw.get("url", ""),
        location=raw.get("location", ""),
        deadline=raw.get("deadline") or None,
        raw_payload="",
    )
