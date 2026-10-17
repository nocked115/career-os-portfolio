"""알림 메일 하나에 든 공고 여러 건을 잘라 낸다 — 사이트를 긁지 않고."""

from app.services import posting_parser


MAIL = """회원님께 추천하는 맞춤 공고

[카카오] 데이터 사이언티스트 신입 채용
마감 2026-10-02
https://example.com/jobs/1

[네이버] Data Engineer (신입/경력)
마감 2026-10-10
https://example.com/jobs/2

[토스] 머신러닝 엔지니어
마감 2026-09-30
https://example.com/jobs/3

수신거부
"""


def test_a_mail_splits_into_one_block_per_posting():
    blocks = posting_parser.split_postings(MAIL)

    assert len(blocks) == 3
    assert blocks[0].startswith("[카카오]")
    assert "example.com/jobs/2" in blocks[1]
    # 머리말 · 꼬리말은 공고가 아니다.
    assert not any("수신거부" in block for block in blocks)


def test_postings_that_run_together_split_at_the_link():
    text = "\n".join([
        "[카카오] 데이터 사이언티스트",
        "https://example.com/jobs/1",
        "[네이버] Data Engineer",
        "https://example.com/jobs/2",
    ])

    blocks = posting_parser.split_postings(text)

    assert len(blocks) == 2
    assert "카카오" in blocks[0] and "네이버" not in blocks[0]


def test_a_single_posting_is_left_alone(client):
    one = "\n".join([
        "데이터 분석가 채용",
        "테스트회사",
        "지원 자격: 학사 이상",
        "마감 2026-10-02",
        "https://example.com/jobs/1",
    ])

    assert posting_parser.split_postings(one) == []
    assert client.post("/opportunities/split", json={"text": one}).json()["count"] == 0


def test_split_endpoint_returns_each_block(client):
    body = client.post("/opportunities/split", json={"text": MAIL}).json()

    assert body["count"] == 3
    assert all(block.strip() for block in body["blocks"])


def test_numbered_lists_keep_the_details_under_each_title():
    """실제로 받는 모양 — 번호 제목, 그 밑에 링크, 그 아래 상세.

    링크에서 자르면 마감 · 근무지 · 자격이 통째로 뒤 토막에 남고, 그
    토막은 링크가 없어서 버려진다. 넣는 공고마다 마감이 비어 있던 게
    그래서였다.
    """
    text = """1. 신플렛 — 이미지 딥러닝 Python 개발자 신입
https://m.saramin.co.kr/job-search/view?rec_idx=55011629

* 형태·근무지: 정규직 / 서울 서초구.
* 마감: 2026년 10월 11일 23:59.

2. 하쿠호도제일 — AI 데이터분석팀 인턴
https://m.saramin.co.kr/job-search/view?rec_idx=55146851

* 형태·근무지: 6개월 인턴 / 서울 마포구.
* 마감: 2026년 10월 16일.
"""

    blocks = posting_parser.split_postings(text)

    assert len(blocks) == 2
    assert "2026년 10월 11일" in blocks[0]
    assert "서초구" in blocks[0]
    assert "2026년 10월 16일" in blocks[1]
    assert "마포구" in blocks[1]
    # 뒤 공고의 상세가 앞 공고로 새어 들어오면 안 된다.
    assert "마포구" not in blocks[0]


def test_a_mail_alert_still_splits_at_the_link():
    """번호가 없으면 예전 규칙 그대로 — 한 공고가 링크로 끝난다."""
    text = """한빛전자 데이터 분석가
서울 강남구
https://example.com/jobs/1
두손컴퍼니 ML 엔지니어
경기 성남시
https://example.com/jobs/2
"""

    blocks = posting_parser.split_postings(text)

    assert len(blocks) == 2
    assert "한빛전자" in blocks[0] and "두손컴퍼니" not in blocks[0]
    assert "두손컴퍼니" in blocks[1]
