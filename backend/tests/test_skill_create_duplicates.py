"""스킬 추가 — 같은 스킬을 두 번 만들지 않는다."""


def test_the_same_skill_cannot_be_added_twice(client):
    first = client.post("/skills", json={"name": " Machine Learning ", "category": "ai", "level": 2})
    assert first.status_code == 200
    assert first.json()["name"] == "Machine Learning"

    again = client.post("/skills", json={"name": "machinelearning", "category": "ai"})
    assert again.status_code == 409
    assert "Machine Learning" in again.json()["detail"]


def test_a_blank_name_is_refused(client):
    assert client.post("/skills", json={"name": "   ", "category": "ai"}).status_code == 422
