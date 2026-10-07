"""전공(도구) · 교양(배경지식) 구분.

수현: "대학교의 교양과 전공처럼 — CS 지식 이런 것들은 교양쪽으로,
책 읽고 정리하기 이 정도."

한 줄에 세우면 "Infrastructure 21%" 가 맨 위에 올라오는데 그걸 보고
뭘 공부할지는 알 수 없다. 공고에서 실제로 세어지는 건 GCP · BigQuery
같은 구체적인 도구다.
"""

from app import models
from app.services import priority


def test_a_new_skill_is_a_tool_by_default(client):
    """지금 등록된 것은 전부 도구로 넣어 둔 것이다. 교양으로 내리는 건 사람이 정한다."""
    body = client.post("/skills", json={"name": "Airflow", "category": "data"}).json()

    assert body["track"] == "major"


def test_a_skill_can_be_moved_to_general(client):
    created = client.post("/skills", json={"name": "운영체제", "category": "cs"}).json()

    body = client.patch(f"/skills/{created['id']}", json={"track": "general"}).json()

    assert body["track"] == "general"


def test_an_unknown_track_is_refused(client):
    created = client.post("/skills", json={"name": "자료구조", "category": "cs"}).json()

    assert client.patch(
        f"/skills/{created['id']}", json={"track": "교양"}
    ).status_code == 422


def test_priority_is_split_by_track_without_changing_scores(db_session):
    """점수는 안 깎는다 — 교양이라고 수요를 낮다고 말하면 그건 거짓이다.

    세는 건 그대로 두고 **놓는 자리**를 나눈다.
    """
    db_session.add(models.Skill(name="Python", category="programming", level=1))
    db_session.add(models.Skill(
        name="Infrastructure", category="infra", level=0,
        track=models.TRACK_GENERAL,
    ))
    db_session.commit()

    flat = {row["skill"]: row for row in priority.get_learning_priority(db_session)}
    split = priority.get_learning_priority_by_track(db_session)

    assert [row["skill"] for row in split["major"]] == ["Python"]
    assert [row["skill"] for row in split["general"]] == ["Infrastructure"]

    # 나눠도 점수는 그대로여야 한다.
    for group in split.values():
        for row in group:
            assert row["priority_score"] == flat[row["skill"]]["priority_score"]


def test_the_priority_payload_carries_the_track(db_session):
    db_session.add(models.Skill(name="SQL", category="data", level=2))
    db_session.commit()

    assert priority.get_learning_priority(db_session)[0]["track"] == "major"
