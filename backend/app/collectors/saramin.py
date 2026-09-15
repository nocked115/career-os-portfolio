"""사람인 채용정보 API 수집원.

공식 API 다 (https://oapi.saramin.co.kr). 스크래핑하지 않는다.

약관에서 지켜야 하는 것 (https://oapi.saramin.co.kr/caution):
- 하루 최대 500회 호출. 키워드마다 1회라 하루 몇 번이면 충분하다
- 출처를 표시한다. source="saramin" 으로 저장하고 화면이 "사람인" 을 붙인다
- 재판매·유료화 금지. 그래서 공개 데모에서는 켜지 않는다
- access-key 를 공개하지 않는다. .env 에만 둔다

응답에는 **공고 본문이 없다.** 직무명·키워드·경력 같은 필드만 온다.
그 필드들로 description 을 채워 스킬을 찾되, 본문을 지어내지 않는다.
그래서 손으로 넣은 공고보다 스킬 연결이 얕다.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from .. import auth
from . import base


SOURCE_NAME = "saramin"

ENDPOINT = "https://oapi.saramin.co.kr/job-search"

# 한 번에 받을 수 있는 최대치 (API 문서).
PAGE_SIZE = 110

DEFAULT_KEYWORDS = "데이터 분석,머신러닝,인공지능"

# close-type 1 만 "접수 마감일" 이다. 2 채용 시, 3 상시, 4 수시 에는
# expiration-timestamp 가 와도 진짜 마감이 아니다. 마감으로 넣으면
# 오늘 계획에 가짜 D-day 가 올라온다.
CLOSE_TYPE_DEADLINE = "1"

# 사람인 API 가 돌려주는 오류 코드 (API 문서).
ERROR_CODES = {
    1: "access-key 가 없습니다",
    2: "access-key 가 유효하지 않습니다",
    3: "요청 파라미터가 잘못됐습니다",
    4: "하루 호출 한도를 넘었습니다",
    99: "사람인 시스템 오류입니다",
}


def _key() -> str:
    return os.getenv("SARAMIN_API_KEY", "").strip()


def keywords() -> list[str]:
    raw = os.getenv("CAREER_OS_SARAMIN_KEYWORDS", DEFAULT_KEYWORDS)

    return [word.strip() for word in raw.split(",") if word.strip()]


def is_available() -> bool:
    """키가 있고, 공개 데모가 아닐 때만.

    공개 데모에 사람인 공고를 싣는 것은 약관의 재배포 금지에 걸린다.
    """
    return bool(_key()) and not auth.is_public_demo()


def _get(params: dict) -> dict:
    query = urllib.parse.urlencode({"access-key": _key(), **params})
    request = urllib.request.Request(
        f"{ENDPOINT}?{query}", headers={"Accept": "application/json"}
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        try:
            data = json.loads(error.read().decode())
        except ValueError:
            raise base.CollectorError(f"사람인 HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        # 오류 메시지에 URL 이 들어가면 키가 로그에 남는다. 종류만 남긴다.
        raise base.CollectorError(
            f"사람인에 연결하지 못했습니다 ({type(error).__name__})"
        ) from None

    code = (data.get("result") or {}).get("code") if isinstance(
        data.get("result"), dict
    ) else data.get("code")

    if code:
        raise base.CollectorError(
            ERROR_CODES.get(int(code), f"사람인 오류 코드 {code}")
        )

    return data


def fetch() -> list[dict]:
    """키워드마다 한 번씩 부른다. 같은 공고가 겹치면 한 번만 남긴다."""
    # 키가 없으면 요청을 보내지 않는다. 보내면 사람인이 "키 없음" 을
    # 돌려주는데, 그 한 번도 외부 호출이다 — 테스트에서 실제로 나갔다.
    if not _key():
        raise base.CollectorError(ERROR_CODES[1])

    seen = {}

    for word in keywords():
        data = _get({
            "keywords": word,
            "count": PAGE_SIZE,
            "sort": "pd",
            "fields": "expiration-date",
        })

        for job in (data.get("jobs") or {}).get("job") or []:
            if str(job.get("active")) != "1":
                continue

            seen.setdefault(str(job.get("id")), job)

    return list(seen.values())


def _name(node) -> str:
    return (node or {}).get("name", "") if isinstance(node, dict) else ""


def _deadline(job: dict):
    if str((job.get("close-type") or {}).get("code")) != CLOSE_TYPE_DEADLINE:
        return None

    stamp = job.get("expiration-timestamp")

    try:
        return datetime.fromtimestamp(int(stamp)) if stamp else None
    except (TypeError, ValueError):
        return None


def normalize(raw: dict) -> dict:
    position = raw.get("position") or {}

    # 본문이 없으므로 API 가 준 분류·키워드만 이어 붙인다.
    # 스킬 추출기가 이 텍스트에서 "머신러닝" 같은 별칭을 찾는다.
    lines = [
        f"직무: {_name(position.get('job-mid-code'))} / "
        f"{_name(position.get('job-code'))}",
        f"키워드: {raw.get('keyword', '')}",
        f"경력: {_name(position.get('experience-level'))}",
        f"학력: {_name(position.get('required-education-level'))}",
        f"업종: {_name(position.get('industry'))}",
        f"마감 형태: {_name(raw.get('close-type'))}",
        "출처: 사람인",
    ]

    return base.normalize_opportunity(
        source=SOURCE_NAME,
        external_id=raw.get("id"),
        title=position.get("title", ""),
        organization=_name((raw.get("company") or {}).get("detail")),
        description="\n".join(line for line in lines if not line.endswith(": ")),
        url=raw.get("url", ""),
        location=_name(position.get("location")),
        employment_type=_name(position.get("job-type")),
        deadline=_deadline(raw),
        raw_payload=json.dumps(raw, ensure_ascii=False),
    )
