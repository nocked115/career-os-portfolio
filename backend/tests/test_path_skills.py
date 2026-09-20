"""한 경로가 여러 스킬을 키운다 — 논문 스터디는 PyTorch 와 Computer Vision 을 같이 키운다."""

from app import models
from app.services import learning as learning_service
from app.services import priority as priority_service


def _skill(client, name):
    return client.post("/skills", json={"name": name, "category": "ai", "level": 0}).json()


def test_a_path_can_grow_two_skills(client, db_session):
    torch = _skill(client, "PyTorch")
    vision = _skill(client, "Computer Vision")

    path = client.post("/learning-paths", json={
        "title": "논문 스터디", "skill_ids": [torch["id"], vision["id"]], "progress_percent": 50,
    }).json()

    # 연결 목록의 순서는 보장되지 않는다 (연결 테이블). 대표 스킬만 첫 번째로 정한다.
    assert {skill["name"] for skill in path["skills"]} == {"PyTorch", "Computer Vision"}
    assert path["skill_id"] == torch["id"]

    for name in ("PyTorch", "Computer Vision"):
        skill = db_session.query(models.Skill).filter_by(name=name).one()
        assert [item.title for item in skill.growing_paths] == ["논문 스터디"]
        assert priority_service.calculate_learning_progress(skill) == 50

    # 단계를 넣으면 경로 진행률은 끝낸 단계로 다시 계산된다 (아직 0개 → 0%).
    client.post("/learning-steps", json={
        "learning_path_id": path["id"], "title": "1주차 — CLIP", "position": 0,
    })
    db_session.expire_all()

    for name in ("PyTorch", "Computer Vision"):
        skill = db_session.query(models.Skill).filter_by(name=name).one()
        assert priority_service.calculate_learning_progress(skill) == 0
        assert learning_service.find_next_step(skill).title == "1주차 — CLIP"


def test_links_can_be_changed_and_cleared(client, db_session):
    torch = _skill(client, "PyTorch")
    vision = _skill(client, "Computer Vision")
    path = client.post("/learning-paths", json={"title": "스프린트", "skill_ids": [torch["id"]]}).json()

    swapped = client.patch(f"/learning-paths/{path['id']}", json={"skill_ids": [vision["id"], torch["id"]]}).json()
    assert {skill["name"] for skill in swapped["skills"]} == {"Computer Vision", "PyTorch"}
    # 먼저 준 것이 대표가 된다.
    assert swapped["skill_id"] == vision["id"]

    cleared = client.patch(f"/learning-paths/{path['id']}", json={"skill_ids": []}).json()
    assert cleared["skills"] == []
    assert cleared["skill_id"] is None


def test_an_unknown_skill_is_refused(client):
    path = client.post("/learning-paths", json={"title": "스터디"}).json()

    assert client.patch(f"/learning-paths/{path['id']}", json={"skill_ids": [9999]}).status_code == 404


def test_the_old_single_link_still_counts(client, db_session):
    torch = _skill(client, "PyTorch")
    # skill_ids 없이 만든 예전 경로 (마이그레이션 전에 만들어진 것과 같은 모양)
    client.post("/learning-paths", json={"title": "옛 경로", "skill_id": torch["id"], "progress_percent": 30})
    db_session.expire_all()

    skill = db_session.query(models.Skill).filter_by(name="PyTorch").one()

    assert [path.title for path in skill.growing_paths] == ["옛 경로"]
    assert priority_service.calculate_learning_progress(skill) == 30
