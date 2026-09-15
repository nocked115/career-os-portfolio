"""회고의 한 달 스스로 평가 — 사람이 적은 그대로, 한 달에 하나."""

from datetime import date


def _month(offset=0):
    today = date.today()
    index = today.year * 12 + today.month - 1 + offset
    return index // 12, index % 12 + 1


def test_a_month_without_a_reflection_says_none(client):
    year, month = _month()
    body = client.get(f"/analytics/review?year={year}&month={month}").json()
    assert body["reflection"] is None


def test_saving_twice_updates_the_same_month(client):
    year, month = _month()
    url = f"/analytics/review/reflection?year={year}&month={month}"

    first = client.put(url, json={"rating": 3, "went_well": " 코테 매일 함 ", "to_improve": "Tave 준비 늦음"})
    assert first.status_code == 200
    assert first.json()["went_well"] == "코테 매일 함"

    second = client.put(url, json={"rating": 4, "next_focus": "캡스톤 MVP"}).json()
    assert second["rating"] == 4
    assert second["went_well"] == ""          # 보낸 그대로 — 빈 칸은 빈 칸으로
    assert second["next_focus"] == "캡스톤 MVP"

    review = client.get(f"/analytics/review?year={year}&month={month}").json()
    assert review["reflection"]["rating"] == 4


def test_rating_is_optional_but_bounded(client):
    year, month = _month(-1)
    url = f"/analytics/review/reflection?year={year}&month={month}"

    assert client.put(url, json={"went_well": "적기만"}).json()["rating"] is None
    assert client.put(url, json={"rating": 6}).status_code == 422


def test_future_months_cannot_be_rated(client):
    year, month = _month(1)
    response = client.put(f"/analytics/review/reflection?year={year}&month={month}", json={"rating": 5})
    assert response.status_code == 400
