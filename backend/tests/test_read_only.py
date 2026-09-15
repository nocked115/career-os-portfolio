"""읽기 전용 배포본.

데모는 비밀번호를 포트폴리오에 공개한다. 그 비밀번호를 아는
사람이 데이터를 갈아엎을 수 있으면 안 된다.
"""

import pytest

from app import auth, models


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setenv(auth.READ_ONLY_VAR, "1")


def test_reading_still_works(client, demo):
    """구경은 다 되어야 한다. 그게 데모의 목적이다."""
    assert client.get("/skills").status_code == 200
    assert client.get("/today").status_code == 200
    assert client.get("/universe").status_code == 200


def test_writing_is_refused(client, demo):
    created = client.post(
        "/skills", json={"name": "훼손", "category": "x"}
    )

    assert created.status_code == 403
    assert "구경용" in created.json()["detail"]


def test_every_write_method_is_refused(client, db_session, demo):
    skill = models.Skill(name="Python", category="lang")
    db_session.add(skill)
    db_session.commit()

    assert client.post("/skills", json={"name": "새것", "category": "x"}).status_code == 403
    assert client.patch(f"/skills/{skill.id}", json={"level": 99}).status_code == 403
    assert client.delete(f"/skills/{skill.id}").status_code == 403

    # 진짜로 안 바뀌었는지 본다. 403 을 주고 몰래 쓰면 최악이다.
    db_session.refresh(skill)
    assert skill.level in (0, None)
    assert db_session.query(models.Skill).count() == 1


def test_transfer_import_is_refused(client, demo):
    """요청 한 번으로 데모를 통째로 비울 수 있던 경로다."""
    payload = client.get("/transfer/export").json()

    response = client.post(
        "/transfer/import?confirm=REPLACE", json=payload
    )

    assert response.status_code == 403


def test_off_by_default(client):
    """실사용 배포본과 로컬은 아무 영향이 없어야 한다."""
    assert not auth.is_read_only()

    assert client.post(
        "/skills", json={"name": "쓸 수 있다", "category": "x"}
    ).status_code in (200, 201)


@pytest.mark.parametrize("value,blocked", [
    ("1", True), ("true", True), ("yes", True),
    ("0", False), ("false", False), ("", False),
])
def test_the_variable_reads_the_way_people_expect(monkeypatch, value, blocked):
    """0 이나 false 로 꺼두려던 사람이 켜지면 안 된다."""
    monkeypatch.setenv(auth.READ_ONLY_VAR, value)

    assert auth.is_read_only() is blocked


def test_config_tells_the_frontend(client, demo):
    """화면이 이걸 모르면 버튼이 먹통인 고장난 앱으로 보인다."""
    assert client.get("/config").json() == {"read_only": True}


# --------------------------------
# 공개 데모 — 자격 증명 없이 여는 포트폴리오용
# --------------------------------

@pytest.fixture
def public_demo(monkeypatch):
    monkeypatch.setenv("CAREER_OS_ENV", "production")
    monkeypatch.setenv(auth.PUBLIC_DEMO_VAR, "1")
    monkeypatch.delenv(auth.USER_VAR, raising=False)
    monkeypatch.delenv(auth.PASSWORD_VAR, raising=False)


def test_public_demo_may_start_without_credentials(public_demo):
    """링크 하나로 열려야 한다. 비밀번호를 옮겨 치게 하면 이탈한다."""
    auth.check_startup()  # 예외가 나면 실패다


def test_production_still_refuses_to_start_without_credentials(monkeypatch):
    """공개 데모라고 말하지 않았으면 규칙은 그대로다."""
    monkeypatch.setenv("CAREER_OS_ENV", "production")
    monkeypatch.delenv(auth.PUBLIC_DEMO_VAR, raising=False)
    monkeypatch.delenv(auth.USER_VAR, raising=False)
    monkeypatch.delenv(auth.PASSWORD_VAR, raising=False)

    with pytest.raises(RuntimeError):
        auth.check_startup()


def test_public_demo_is_always_read_only(public_demo):
    """공개인데 쓰기 가능은 있을 수 없다.

    READ_ONLY 를 따로 켜지 않아도 쓰기가 막혀야 한다. 안 그러면
    링크를 아는 누구나 /transfer/import 한 번으로 데모를 비운다.
    """
    assert auth.is_read_only()


def test_public_demo_opens_reading_and_blocks_writing(client, public_demo):
    assert client.get("/skills").status_code == 200
    assert client.get("/universe").status_code == 200

    assert client.post(
        "/skills", json={"name": "훼손", "category": "x"}
    ).status_code == 403

    assert client.post(
        "/transfer/import?confirm=REPLACE", json={}
    ).status_code == 403


def test_read_only_alone_does_not_open_the_door(monkeypatch):
    """읽기 전용은 인증을 풀지 않는다. 그건 PUBLIC_DEMO 의 몫이다."""
    monkeypatch.setenv("CAREER_OS_ENV", "production")
    monkeypatch.setenv(auth.READ_ONLY_VAR, "1")
    monkeypatch.delenv(auth.PUBLIC_DEMO_VAR, raising=False)
    monkeypatch.delenv(auth.USER_VAR, raising=False)
    monkeypatch.delenv(auth.PASSWORD_VAR, raising=False)

    with pytest.raises(RuntimeError):
        auth.check_startup()
