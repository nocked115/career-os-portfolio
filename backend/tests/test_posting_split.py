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
