"""서가 · HOT · 오늘 학습에 꺼내기.

서가(언제 보는가)와 중요도(얼마나 중요한가)를 섞지 않는다.
사람이 정하지 않은 서가는 기록으로만 정하고 이유를 준다.
HOT 순위는 기록이 있을 때만 생긴다.
"""

from datetime import datetime, timedelta


def _skill(client, name="AWS"):
    return client.post("/skills", json={"name": name, "category": "x", "level": 0}).json()


def _resource(client, skill, title="AWS 교재", resource_type="book"):
    return client.post(
        "/resources",
        json={
            "title": title,
            "resource_type": resource_type,
            "ownership": "owned",
            "url": None,
            "skill_id": skill["id"],
        },
    ).json()


def _segment(client, resource, label, position, minutes=30):
    return client.post(
        f"/resources/{resource['id']}/segments",
        json={"label": label, "position": position, "estimated_minutes": minutes},
    ).json()


def _item(client, resource):
    items = client.get("/library").json()["items"]
    return next(item for item in items if item["id"] == resource["id"])


def test_an_untouched_resource_is_not_sorted_yet(client):
    resource = _resource(client, _skill(client))

    item = _item(client, resource)

    assert item["shelf"] == "saved"
    assert item["shelf_label"] == "분류 전"
    assert item["progress"]["percent"] is None


def test_finishing_a_chapter_puts_it_on_the_now_shelf_with_a_reason(client):
    resource = _resource(client, _skill(client))
    first = _segment(client, resource, "1장", 0)
    _segment(client, resource, "2장", 1)

    client.post(f"/segments/{first['id']}/complete")

    item = _item(client, resource)

    assert item["shelf"] == "in_progress"
    assert "챕터 1개" in item["shelf_reason"]
    assert item["progress"]["percent"] == 50
    assert item["progress"]["next"] == "2장"


def test_a_resource_on_an_unfinished_step_is_next(client):
    skill = _skill(client)
    resource = _resource(client, skill)
    path = client.post("/learning-paths", json={"title": "AWS", "skill_id": skill["id"]}).json()
    step = client.post(
        "/learning-steps",
        json={"learning_path_id": path["id"], "title": "EC2", "position": 0},
    ).json()
    client.post(f"/learning-steps/{step['id']}/resources/{resource['id']}")

    assert _item(client, resource)["shelf"] == "queued"


def test_a_shelf_chosen_by_hand_wins(client):
    resource = _resource(client, _skill(client))
    chapter = _segment(client, resource, "1장", 0)
    client.post(f"/segments/{chapter['id']}/complete")

    moved = client.post(f"/resources/{resource['id']}/shelf?to=on_hold").json()

    assert moved["shelf"] == "on_hold"
    assert moved["shelf_reason"] == "직접 정한 서가"


def test_an_unknown_shelf_is_rejected(client):
    resource = _resource(client, _skill(client))

    assert client.post(f"/resources/{resource['id']}/shelf?to=someday").status_code == 422


def test_hot_ranks_come_only_from_recent_records(client, db_session):
    from app import models

    skill = _skill(client)
    busy = _resource(client, skill, "많이 본 책")
    quiet = _resource(client, skill, "한 번 본 영상", "video")
    old = _resource(client, skill, "예전에 본 책")

    for index in range(2):
        chapter = _segment(client, busy, f"{index + 1}장", index)
        client.post(f"/segments/{chapter['id']}/complete")

    once = _segment(client, quiet, "1강", 0)
    client.post(f"/segments/{once['id']}/complete")

    long_ago = _segment(client, old, "1장", 0)
    client.post(f"/segments/{long_ago['id']}/complete")
    row = db_session.get(models.LearningResourceSegment, long_ago["id"])
    row.completed_at = datetime.now() - timedelta(days=40)
    db_session.commit()

    hot = client.get("/library").json()["hot"]

    assert [(entry["rank"], entry["resource_id"]) for entry in hot] == [
        (1, busy["id"]),
        (2, quiet["id"]),
    ]
    assert "챕터 2개" in hot[0]["reason"]


def test_no_records_means_no_hot_list(client):
    _resource(client, _skill(client))

    assert client.get("/library").json()["hot"] == []


def test_taking_a_resource_out_puts_its_next_chapter_on_today(client):
    skill = _skill(client)
    resource = _resource(client, skill)
    done = _segment(client, resource, "1장", 0)
    _segment(client, resource, "2장", 1, minutes=40)
    client.post(f"/segments/{done['id']}/complete")

    path = client.post("/learning-paths", json={"title": "AWS", "skill_id": skill["id"]}).json()
    step = client.post(
        "/learning-steps",
        json={"learning_path_id": path["id"], "title": "EC2", "position": 0},
    ).json()
    client.post(f"/learning-steps/{step['id']}/resources/{resource['id']}")

    body = client.post(f"/resources/{resource['id']}/add-to-plan").json()

    assert body["already_planned"] is False
    assert body["task"]["title"] == "AWS 교재 — 2장"
    assert body["task"]["minutes"] == 40
    assert body["session_step"]["id"] == step["id"]
    assert body["resource"]["shelf"] == "in_progress"

    today = client.get("/today/plan").json()["tasks"]
    assert [task["title"] for task in today] == ["AWS 교재 — 2장"]

    again = client.post(f"/resources/{resource['id']}/add-to-plan").json()
    assert again["already_planned"] is True
