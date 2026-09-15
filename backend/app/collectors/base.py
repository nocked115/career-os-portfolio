"""수집원 어댑터 계약.

Career OS 의 비즈니스 로직은 특정 채용 플랫폼에 의존하면 안 된다.
모든 수집원은 여기 정의된 형태로 정규화해서 내놓고,
그다음부터는 Opportunity 하나로만 다룬다.

    외부 소스 → fetch() → normalize() → Opportunity → Career OS
"""

from datetime import datetime


# job_event: 취업박람회 · 채용설명회. 지원하는 공고가 아니라 가는 행사다 (마감일 = 행사 마지막 날).
OPPORTUNITY_TYPES = ("job", "competition", "external_activity", "job_event")


class CollectorError(Exception):
    """수집원이 정상적으로 응답하지 못했을 때."""


def parse_deadline(value):
    """수집원마다 다른 마감일 표기를 datetime 으로 맞춘다.

    해석할 수 없으면 None. 임의의 날짜를 만들어내지 않는다.
    """
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    # "%Y%m%d" 은 고용24 (예: 20260927).
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%dT%H:%M:%S", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def normalize_opportunity(
    *,
    source: str,
    external_id,
    title: str,
    opportunity_type: str = "job",
    organization: str = "",
    role: str = "",
    description: str = "",
    url: str = "",
    location: str = "",
    employment_type: str = "",
    deadline=None,
    raw_payload: str = "",
) -> dict:
    """수집원의 원본 데이터를 Opportunity 필드로 옮긴다.

    필수는 source 와 title 뿐이다.
    나머지가 비어 있으면 비운 채로 둔다. 추측해서 채우지 않는다.
    """
    if not source:
        raise CollectorError("source is required")

    if not title:
        raise CollectorError("title is required")

    if opportunity_type not in OPPORTUNITY_TYPES:
        raise CollectorError(
            f"unknown opportunity_type: {opportunity_type}"
        )

    return {
        "source": source,
        "source_external_id": (
            str(external_id) if external_id is not None else None
        ),
        "opportunity_type": opportunity_type,
        "title": title,
        "organization": organization or "",
        "role": role or "",
        "description": description or "",
        "source_url": url or "",
        "location": location or "",
        "employment_type": employment_type or "",
        "deadline": parse_deadline(deadline),
        "raw_payload": raw_payload or "",
    }
