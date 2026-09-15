"""Basic Auth.

이 앱에는 사용자 모델이 없다. 인증은 "이 배포본에 접근할 수 있는가"
하나만 판단한다. 실수 한 번이 커리어 데이터 전체를 공개하는
지점이라 여기는 촘촘히 막는다.
"""

import base64

import pytest

from app import auth


def _header(user, password):
    raw = f"{user}:{password}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


@pytest.fixture
def secured(monkeypatch):
    monkeypatch.setenv("CAREER_OS_AUTH_USER", "hyun")
    monkeypatch.setenv("CAREER_OS_AUTH_PASSWORD", "long-enough-secret")
    return _header("hyun", "long-enough-secret")


def test_production_refuses_to_start_without_credentials(monkeypatch):
    """기본 비밀번호를 두면 그게 곧 공개 배포다.

    조용히 인증을 끄는 것보다 안 뜨는 편이 낫다.
    """
    monkeypatch.setenv("CAREER_OS_ENV", "production")
    monkeypatch.delenv("CAREER_OS_AUTH_USER", raising=False)
    monkeypatch.delenv("CAREER_OS_AUTH_PASSWORD", raising=False)

    with pytest.raises(RuntimeError) as raised:
        auth.check_startup()

    message = str(raised.value)

    # "둘 중 뭐가 없다" 가 아니라 무엇이 없는지 말해야 한다.
    # 배포 실패 로그에서 이 한 줄 차이가 왕복 한 번을 줄인다.
    assert auth.USER_VAR in message
    assert auth.PASSWORD_VAR in message


def test_production_starts_when_credentials_are_set(monkeypatch):
    monkeypatch.setenv("CAREER_OS_ENV", "production")
    monkeypatch.setenv("CAREER_OS_AUTH_USER", "hyun")
    monkeypatch.setenv("CAREER_OS_AUTH_PASSWORD", "long-enough-secret")

    auth.check_startup()


def test_development_needs_no_credentials(monkeypatch):
    """로컬에서 매번 비밀번호를 묻게 하지 않는다."""
    monkeypatch.delenv("CAREER_OS_ENV", raising=False)
    monkeypatch.delenv("CAREER_OS_AUTH_USER", raising=False)

    auth.check_startup()


def test_requests_are_rejected_without_credentials(client, secured):
    assert client.get("/skills").status_code == 401


def test_the_right_credentials_get_through(client, secured):
    assert client.get("/skills", headers=secured).status_code == 200


@pytest.mark.parametrize(
    "user,password",
    [
        ("hyun", "wrong"),
        ("someone", "long-enough-secret"),
        ("", ""),
        ("hyun", ""),
    ],
)
def test_wrong_credentials_are_rejected(client, secured, user, password):
    response = client.get("/skills", headers=_header(user, password))

    assert response.status_code == 401


def test_a_malformed_header_does_not_crash(client, secured):
    for value in ("Basic", "Basic !!!not-base64!!!", "Bearer token", ""):
        response = client.get("/skills", headers={"Authorization": value})

        assert response.status_code == 401


def test_the_browser_is_told_to_ask(client, secured):
    """WWW-Authenticate 가 없으면 브라우저가 자격 증명을 묻지 않는다."""
    response = client.get("/skills")

    assert "Basic" in response.headers.get("www-authenticate", "")


def test_health_check_stays_open(client, secured):
    """헬스체크가 401 을 받으면 배포가 계속 실패한 것으로 보인다."""
    assert client.get("/healthz").status_code == 200


def test_no_credentials_means_no_gate(client, monkeypatch):
    """로컬 개발에서는 인증이 없다."""
    monkeypatch.delenv("CAREER_OS_AUTH_USER", raising=False)
    monkeypatch.delenv("CAREER_OS_AUTH_PASSWORD", raising=False)

    assert client.get("/skills").status_code == 200



def test_a_value_of_only_spaces_counts_as_missing(monkeypatch):
    """복사해서 붙일 때 공백이 딸려 오는 일이 잦다.

    그대로 두면 값이 있는데도 비밀번호가 안 맞는다. 원인을 찾기
    아주 어려운 종류의 실패다.
    """
    monkeypatch.setenv("CAREER_OS_ENV", "production")
    monkeypatch.setenv("CAREER_OS_AUTH_USER", "   ")
    monkeypatch.setenv("CAREER_OS_AUTH_PASSWORD", "secret")

    with pytest.raises(RuntimeError) as raised:
        auth.check_startup()

    assert auth.USER_VAR in str(raised.value)


def test_surrounding_spaces_are_trimmed(client, monkeypatch):
    """값 앞뒤 공백 때문에 로그인이 안 되면 안 된다."""
    monkeypatch.setenv("CAREER_OS_AUTH_USER", "  hyun  ")
    monkeypatch.setenv("CAREER_OS_AUTH_PASSWORD", " long-enough-secret ")

    assert client.get("/skills", headers=_header("hyun", "long-enough-secret")).status_code == 200


def test_non_ascii_credentials_are_rejected_not_crashed(client, monkeypatch):
    """한글 아이디로 시도하면 401 이어야 한다. 500 이 아니라.

    secrets.compare_digest 는 비-ASCII 문자열을 받으면 TypeError 를
    던진다. 미들웨어 안이라 FastAPI 의 예외 핸들러를 거치지 않고
    그대로 500 이 나갔다. 실제 배포에서 이걸로 한 번 막혔다.
    """
    monkeypatch.setenv("CAREER_OS_AUTH_USER", "hyun")
    monkeypatch.setenv("CAREER_OS_AUTH_PASSWORD", "long-enough-secret")

    response = client.get("/skills", headers=_header("다른아이디", "아무거나"))

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_non_ascii_credentials_can_actually_log_in(client, monkeypatch):
    """한글 비밀번호를 쓴 사람도 자기 배포본에 들어갈 수 있어야 한다."""
    monkeypatch.setenv("CAREER_OS_AUTH_USER", "사용자")
    monkeypatch.setenv("CAREER_OS_AUTH_PASSWORD", "아주-긴-비밀번호-입니다")

    assert client.get(
        "/skills", headers=_header("사용자", "아주-긴-비밀번호-입니다")
    ).status_code == 200

    assert client.get(
        "/skills", headers=_header("사용자", "틀린-비밀번호")
    ).status_code == 401
