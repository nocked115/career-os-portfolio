"""인턴인가 신입(정규)인가.

수현: "채용에 인턴/신입 이거 나눠줄 수 있나?"

employment_type 은 자유 글자라 믿을 수 없다 — 수현 데이터 76건 중 35건이
비어 있고, 나머지도 "정규직|정규직전환형|기간제|기타" 처럼 섞여 온다.
"""

from app import models
from app.services import opportunity as service


def _posting(db, title, employment_type="", favorite=False, org="회사"):
    row = models.Opportunity(
        opportunity_type="job", title=title, organization=org,
        source="test", employment_type=employment_type, favorite=favorite,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_intern_is_read_from_the_title_when_the_field_is_empty(db_session):
    """35건이 고용형태가 비어 있다. 제목에는 적혀 있다."""
    row = _posting(db_session, "Video Agent 연구/개발 (체험형 인턴)")

    assert service.hiring_type(row) == "intern"


def test_newgrad_is_recognised(db_session):
    for title in ("2026년 하반기 신입사원 공개채용", "27년 신입공채", "Junior Talent 채용"):
        assert service.hiring_type(_posting(db_session, title)) == "newgrad"


def test_the_field_is_used_when_the_title_says_nothing(db_session):
    row = _posting(db_session, "데이터 분석", employment_type="인턴")

    assert service.hiring_type(row) == "intern"


def test_intern_wins_when_both_appear(db_session):
    """2027-02 졸업이면 지금 당장 갈 수 있는 쪽이 인턴이다."""
    row = _posting(db_session, "AI 모델 개발 (신입/인턴)")

    assert service.hiring_type(row) == "intern"


def test_unknown_when_nothing_says(db_session):
    """모르는 것은 모른다고 한다. 둘 중 하나로 찍지 않는다."""
    row = _posting(db_session, "Data Engineer")

    assert service.hiring_type(row) == "unknown"


def test_a_favorite_counts_as_a_top_choice(db_session):
    """별을 누른 건 "여기 가고 싶다" 는 가장 분명한 표시인데
    그동안 점수에 아무 영향이 없었다."""
    plain = _posting(db_session, "공고 A", org="모르는회사")
    starred = _posting(db_session, "공고 B", org="모르는회사2", favorite=True)

    assert service.company_preference(db_session, plain)[0] == service.UNKNOWN_PREFERENCE
    assert service.company_preference(db_session, starred)[0] == service.PREFERENCE_VALUE[1]
    assert service.company_preference(db_session, starred)[1] == "즐겨찾기"
