"""단계에서 내가 만든 것, 그리고 그것이 경험으로 남는 길."""

from app import models


def _step(client, db_session):
    path = models.LearningPath(title="Tave 논문 스터디", description="매주 논문 한 편")
    db_session.add(path)
    db_session.flush()

    step = models.LearningStep(
        learning_path_id=path.id, title="1주차 — CLIP 정독", position=0,
        estimated_minutes=60,
    )
    db_session.add(step)
    db_session.commit()
    return step


def test_a_link_is_kept_and_a_file_is_not(client, db_session):
    step = _step(client, db_session)

    created = client.post(f"/learning-steps/{step.id}/outputs", json={
        "title": "CLIP 요약 노트", "url": "https://notion.so/clip-note",
    })
    assert created.status_code == 201
    assert created.json()["url"] == "https://notion.so/clip-note"

    # 주소가 아닌 것은 안 받는다 — 파일 경로도, 스크립트도.
    for bad in ("/Users/hyun/clip.pdf", "javascript:alert(1)", "clip 노트"):
        assert client.post(
            f"/learning-steps/{step.id}/outputs", json={"title": "x", "url": bad}
        ).status_code == 422

    session = client.get(f"/learning-steps/{step.id}/session").json()
    assert [item["title"] for item in session["outputs"]] == ["CLIP 요약 노트"]
    assert session["experience"] is None


def test_the_step_becomes_an_experience_draft(client, db_session):
    step = _step(client, db_session)
    db_session.add_all([
        models.LearningChecklistItem(
            learning_step_id=step.id, position=0, text="Abstract 읽고 정리", done=True
        ),
        models.LearningChecklistItem(
            learning_step_id=step.id, position=1, text="Method 확인", done=False
        ),
    ])
    db_session.commit()

    client.post(f"/learning-steps/{step.id}/outputs", json={
        "title": "요약 노트", "url": "https://notion.so/clip-note",
    })
    client.post(f"/learning-steps/{step.id}/outputs", json={
        "title": "실습 코드", "url": "https://github.com/nocked115/clip-practice",
    })

    sent = client.post(f"/learning-steps/{step.id}/experience")
    assert sent.status_code == 201

    experience = client.get("/experiences").json()
    row = next(item for item in experience if item["id"] == sent.json()["id"])

    assert row["title"] == "Tave 논문 스터디 — 1주차 — CLIP 정독"
    # 체크한 것만 한 일로 옮긴다. 안 한 것은 옮기지 않는다.
    assert "Abstract 읽고 정리" in row["actions"]
    assert "Method 확인" not in row["actions"]
    # 깃허브는 코드 칸, 나머지는 글 칸.
    assert row["github_url"] == "https://github.com/nocked115/clip-practice"
    assert row["blog_url"] == "https://notion.so/clip-note"
    # 사람만 아는 칸은 비워 둔다.
    assert row["problem"] == ""
    assert row["role"] == ""

    # 두 번 보내지 않는다.
    again = client.post(f"/learning-steps/{step.id}/experience")
    assert again.status_code == 409

    session = client.get(f"/learning-steps/{step.id}/session").json()
    assert session["experience"]["id"] == sent.json()["id"]


def test_nothing_made_means_nothing_to_show(client, db_session):
    step = _step(client, db_session)

    refused = client.post(f"/learning-steps/{step.id}/experience")

    assert refused.status_code == 400
    assert "주소를 하나 이상" in refused.json()["detail"]
