"""로컬 개발용 mock 수집원.

실제 외부 연동은 Mission 028 이다. 여기서는 하지 않는다.
새 수집원을 추가할 때 이 파일이 참고 구현이다.
"""

from .. import auth
from . import base


SOURCE_NAME = "mock"


def is_available() -> bool:
    """이 수집원을 지금 쓸 수 있는가.

    실제 소스라면 API 키나 자격 증명 여부를 확인한다.

    **운영에서는 꺼둔다.** 스케줄러가 매일 08:00 에 collect_all 을
    돌리는데, 이게 켜져 있으면 그때마다 가짜 공고가 실제 데이터에
    섞여 들어간다. 수요의 분모가 조용히 오염되고, 그 위에서
    "오늘 뭘 하면 되지?" 가 계산된다.

    실제로 났다 — 손으로 지운 목업 공고 둘이 배포본에서 되살아나
    있었고, 지운 legacy Job 도 함께 돌아와 있었다. 파일 첫 줄에
    "로컬 개발용" 이라고 쓰여 있었지만 코드는 어디서나 True 를
    돌려주고 있었다.
    """
    return not auth.is_production()


def fetch() -> list[dict]:
    """원본 형태 그대로 돌려준다. 정규화는 normalize() 가 한다."""
    return [
        {
            "id": "mock-job-1",
            "company": "Mock Data Company",
            "title": "Data Scientist Intern",
            "role": "data_scientist",
            "employment_type": "intern",
            "url": "https://example.com/mock-job",
            "deadline": "2026-09-30",
            "location": "Seoul",
            "description": (
                "Python, SQL, Statistics and "
                "Machine Learning experience preferred."
            ),
        },
        {
            "id": "mock-competition-1",
            "company": "Mock Data Association",
            "title": "AI 데이터 분석 공모전",
            "kind": "competition",
            "url": "https://example.com/mock-competition",
            "deadline": "2026-10-15",
            "description": (
                "Python, Pandas, Machine Learning 을 활용한 "
                "데이터 분석 공모전입니다."
            ),
        },
    ]


def normalize(raw: dict) -> dict:
    """mock 형식을 Opportunity 필드로 옮긴다."""
    is_competition = raw.get("kind") == "competition"

    return base.normalize_opportunity(
        source=SOURCE_NAME,
        external_id=raw.get("id"),
        opportunity_type=(
            "competition" if is_competition else "job"
        ),
        title=raw.get("title", ""),
        organization=raw.get("company", ""),
        role=raw.get("role", ""),
        description=raw.get("description", ""),
        url=raw.get("url", ""),
        location=raw.get("location", ""),
        employment_type=raw.get("employment_type", ""),
        deadline=raw.get("deadline"),
        raw_payload=str(raw),
    )
