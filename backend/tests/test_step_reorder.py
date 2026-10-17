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


def test_a_new_step_lands_after_the_last_one_even_with_a_gap(client, db_session):
    """수현: "왜 학습에 단계별 추가가 안 먹히냐" — 409 가 줄줄이 났다.

    화면이 steps.length 를 자리 번호로 보냈다. 중간 단계를 지우면 개수는
    줄지만 번호는 그대로라, 7개짜리 경로의 번호가 0~7 이 된다. 거기에
    7 을 보내면 이미 찬 자리라 409 다. 실제로 Tave 논문 스터디와 생성형
    AI 에서 단계를 하나도 못 넣었다.
    """
    path = models.LearningPath(title="Tave 논문 스터디")
    db_session.add(path)
    db_session.flush()
    for position in (0, 1, 3):          # 2번을 지운 자리
        db_session.add(models.LearningStep(
            learning_path_id=path.id, title=f"{position}주차", position=position,
        ))
    db_session.commit()

    created = client.post("/learning-steps", json={
        "learning_path_id": path.id, "title": "4주차",
    })

    assert created.status_code == 201
    assert created.json()["position"] == 4


def test_the_first_step_of_an_empty_path_is_zero(client, db_session):
    path = models.LearningPath(title="빈 경로")
    db_session.add(path)
    db_session.commit()

    created = client.post("/learning-steps", json={
        "learning_path_id": path.id, "title": "1주차",
    })

    assert created.json()["position"] == 0


def test_an_explicit_position_that_is_taken_is_still_refused(client, db_session):
    """자리를 **직접 정해** 보낼 때는 겹침을 그대로 막는다. 조용히 뒤로
    옮기면 순서를 정한 사람의 뜻이 사라진다."""
    path = models.LearningPath(title="코테")
    db_session.add(path)
    db_session.flush()
    db_session.add(models.LearningStep(
        learning_path_id=path.id, title="1일차", position=0,
    ))
    db_session.commit()

    clash = client.post("/learning-steps", json={
        "learning_path_id": path.id, "title": "2일차", "position": 0,
    })

    assert clash.status_code == 409
