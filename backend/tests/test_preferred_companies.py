"""가고 싶은 회사 — 매칭 점수에 얹는다.

목록에 없는 회사를 0 으로 치지 않는다. 목록은 "가고 싶은 곳" 만 적는 칸이라
없다는 것은 싫다가 아니라 아직 모른다다.
"""

from datetime import datetime, timedelta


def _opportunity(client, organization, title="Data Analyst"):
    return client.post("/opportunities", json={
        "opportunity_type": "job",
        "title": title,
        "organization": organization,
        "source": "manual",
        "deadline": (datetime.now() + timedelta(days=20)).isoformat(),
    }).json()


def _company_points(client, opportunity_id):
    match = client.get(f"/opportunities/{opportunity_id}/match").json()
    return match["breakdown"]["company"]


def test_a_company_not_on_the_list_is_unknown_not_zero(client):
    row = _opportunity(client, "들어본 적 없는 회사")

    assert _company_points(client, row["id"]) == 5   # 10 * 0.5 (모름)


def test_a_preferred_company_scores_higher(client):
    client.post("/preferred-companies", json={"name": "Moloco", "rank": 1})
    row = _opportunity(client, "Moloco")

    assert _company_points(client, row["id"]) == 10


def test_rank_changes_how_much_it_helps(client):
    client.post("/preferred-companies", json={"name": "가", "rank": 1})
    client.post("/preferred-companies", json={"name": "나", "rank": 3})

    first = _opportunity(client, "가")
    third = _opportunity(client, "나", title="Analyst II")

    assert _company_points(client, first["id"]) > _company_points(client, third["id"])
    assert _company_points(client, third["id"]) > 5   # 모름보다는 높다


def test_a_posting_without_a_company_name_matches_nothing(client):
    """회사명이 비어 있으면 어느 회사에도 걸리지 않는다.

    "한쪽이 다른 쪽을 품는지" 로 보기 때문에, 빈 문자열은 **모든** 이름에 들어간다.
    막지 않으면 회사명 없는 공고(박람회 · 공고 묶음)가 등록한 회사 전부에 걸려
    점수가 통째로 올라간다.
    """
    client.post("/preferred-companies", json={"name": "삼성", "rank": 1})
    row = _opportunity(client, "")

    assert _company_points(client, row["id"]) == 5   # 모름


def test_a_division_suffix_still_matches(client):
    """공고의 회사명에는 부문이 붙어 온다 — 완전일치로 보면 놓친다."""
    client.post("/preferred-companies", json={"name": "CJ ENM", "rank": 1})
    row = _opportunity(client, "CJ ENM 엔터테인먼트부문")

    assert _company_points(client, row["id"]) == 10


def test_the_breakdown_still_adds_up(client):
    client.post("/preferred-companies", json={"name": "Moloco", "rank": 1})
    row = _opportunity(client, "Moloco")

    match = client.get(f"/opportunities/{row['id']}/match").json()

    assert sum(match["breakdown"].values()) == match["match_score"]


def test_the_same_company_is_not_added_twice(client):
    client.post("/preferred-companies", json={"name": "Moloco"})
    again = client.post("/preferred-companies", json={"name": "Moloco"})

    assert again.status_code == 409


def test_a_company_can_be_removed(client):
    made = client.post("/preferred-companies", json={"name": "Moloco", "rank": 1}).json()
    row = _opportunity(client, "Moloco")
    assert _company_points(client, row["id"]) == 10

    client.delete(f"/preferred-companies/{made['id']}")

    assert _company_points(client, row["id"]) == 5   # 다시 모름
