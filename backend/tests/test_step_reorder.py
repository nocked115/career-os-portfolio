"""단계 순서를 사람이 정한다.

앱이 마감이나 등록 순서로 줄 세우면 "앞 수업을 못 들어서 복습부터 해야
하는" 같은 사정을 넣을 자리가 없다. 실제로 추천시스템 경로에서
'1–2주차 복습' 이 3번째에 박혀 있었다.
"""

from app import models


def _path_with_steps(db, titles):
    path = models.LearningPath(title="추천시스템")
    db.add(path)
    db.flush()

    for position, title in enumerate(titles):
        db.add(models.LearningStep(
            learning_path_id=path.id, title=title,
            position=position, estimated_minutes=60,
        ))

    db.commit()
    db.refresh(path)
    return path


def _titles(path):
    return [s.title for s in sorted(path.steps, key=lambda s: s.position)]


def test_steps_can_be_reordered(client, db_session):
    path = _path_with_steps(db_session, ["3주차", "4주차", "1-2주차 복습", "5주차"])
    by_title = {s.title: s.id for s in path.steps}

    order = [by_title[t] for t in ["1-2주차 복습", "3주차", "4주차", "5주차"]]

    body = client.post(
        f"/learning-paths/{path.id}/steps/reorder", json={"step_ids": order}
    ).json()

    assert [s["title"] for s in body["steps"]] == [
        "1-2주차 복습", "3주차", "4주차", "5주차"
    ]
    assert [s["position"] for s in body["steps"]] == [0, 1, 2, 3]

    db_session.expire_all()
    assert _titles(path)[0] == "1-2주차 복습"


def test_swapping_two_steps_does_not_collide(client, db_session):
    """(path, position) 이 유니크라 한 단계씩 PATCH 로는 못 맞바꾼다.

    중간에 반드시 겹치는 순간이 생기고 거기서 409 가 난다.
    """
    path = _path_with_steps(db_session, ["A", "B"])
    by_title = {s.title: s.id for s in path.steps}

    response = client.post(
        f"/learning-paths/{path.id}/steps/reorder",
        json={"step_ids": [by_title["B"], by_title["A"]]},
    )

    assert response.status_code == 200
    assert [s["title"] for s in response.json()["steps"]] == ["B", "A"]


def test_a_partial_order_is_refused(client, db_session):
    """빠뜨린 단계가 어디로 갈지 정할 방법이 없다. 통째로 받는다."""
    path = _path_with_steps(db_session, ["A", "B", "C"])
    first = sorted(path.steps, key=lambda s: s.position)[0]

    assert client.post(
        f"/learning-paths/{path.id}/steps/reorder", json={"step_ids": [first.id]}
    ).status_code == 400


def test_a_step_from_another_path_is_refused(client, db_session):
    path = _path_with_steps(db_session, ["A", "B"])
    other = _path_with_steps(db_session, ["X", "Y"])

    mixed = [path.steps[0].id, other.steps[0].id]

    assert client.post(
        f"/learning-paths/{path.id}/steps/reorder", json={"step_ids": mixed}
    ).status_code == 400
