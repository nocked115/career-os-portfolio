"""Basic Auth.

이 앱에는 사용자 모델이 없다. 1인용이고, 로그인 화면도 세션도 없다.
그래서 인증은 "이 배포본에 접근할 수 있는가" 하나만 판단한다.

로컬에서는 끈다. 배포에서는 **자격 증명이 없으면 아예 뜨지 않는다** —
기본 비밀번호를 두면 그게 곧 공개 배포다.
"""

import os
import secrets

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# 이 경로들은 인증 없이 연다. 로드밸런서 헬스체크가 401 을 받으면
# 배포가 계속 실패한 것으로 보인다.
PUBLIC_PATHS = ("/healthz",)

REALM = 'Basic realm="Career OS", charset="UTF-8"'


USER_VAR = "CAREER_OS_AUTH_USER"
PASSWORD_VAR = "CAREER_OS_AUTH_PASSWORD"
READ_ONLY_VAR = "CAREER_OS_READ_ONLY"
PUBLIC_DEMO_VAR = "CAREER_OS_PUBLIC_DEMO"

# 읽기 전용에서 막을 메서드. GET/HEAD/OPTIONS 는 통과시킨다.
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _value(name: str) -> str:
    """환경변수 값. 앞뒤 공백은 버린다.

    복사해서 붙일 때 공백이 딸려 오는 일이 잦은데, 그러면 값이
    있는데도 비밀번호가 안 맞는다. 원인을 찾기 아주 어렵다.
    """
    return os.getenv(name, "").strip()


def missing() -> list[str]:
    """비어 있는 자격 증명 변수 이름.

    "둘 중 뭐가 없다" 가 아니라 **무엇이** 없는지 말한다.
    배포 실패 로그에서 이 한 줄 차이가 왕복 한 번을 줄인다.
    """
    return [name for name in (USER_VAR, PASSWORD_VAR) if not _value(name)]


def credentials() -> tuple[str, str] | None:
    """설정된 자격 증명. 없으면 None (= 인증 끔)."""
    if missing():
        return None

    return _value(USER_VAR), _value(PASSWORD_VAR)


def is_production() -> bool:
    return os.getenv("CAREER_OS_ENV", "development") == "production"


def _flag(name: str) -> bool:
    return _value(name).lower() not in ("", "0", "false", "no", "off")


def is_public_demo() -> bool:
    """자격 증명 없이 열어두는 포트폴리오 데모인가.

    데모에 비밀번호를 걸면 링크를 연 사람이 README 로 돌아가
    아이디를 옮겨 쳐야 한다. 거기서 대부분 이탈한다. 데모
    데이터는 전부 지어낸 것이라 숨길 것도 없다.

    READ_ONLY 와 따로 둔 이유: 이 변수는 "인증 없이 연다" 는
    뜻이고, 실사용 서비스에 실수로 들어가면 진짜 경력 기록이
    그대로 공개된다. 이름만 봐도 무슨 일이 벌어지는지 알아야 한다.
    """
    return _flag(PUBLIC_DEMO_VAR)


def is_read_only() -> bool:
    """이 배포본이 구경용인가.

    공개 데모는 반드시 읽기 전용이다. "공개인데 쓰기 가능" 은
    있을 수 없다 — 링크를 아는 누구나 /transfer/import 한 번으로
    데모를 비울 수 있게 된다.
    """
    return is_public_demo() or _flag(READ_ONLY_VAR)


def check_startup() -> None:
    """배포인데 자격 증명이 없으면 뜨지 않는다.

    기본값을 두거나 조용히 인증을 끄면, 실수 한 번에 커리어 데이터
    전체가 공개된다. 시작을 막는 편이 낫다.
    """
    if not is_production():
        return

    # 공개 데모는 자격 증명 없이 떠도 된다. 대신 is_read_only 가
    # 참이 되어 쓰기가 전부 막힌다.
    if is_public_demo():
        return

    absent = missing()

    if absent:
        raise RuntimeError(
            "CAREER_OS_ENV=production 인데 다음 환경변수가 비어 있습니다: "
            + ", ".join(absent)
            + ". 자격 증명 없이 배포하면 누구나 볼 수 있어 시작을 멈춥니다. "
            "(이름의 밑줄과 대소문자를 그대로 맞추고, 값에 공백이 "
            "딸려 오지 않았는지 확인하세요.)"
        )


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        expected = credentials()

        # 자격 증명이 설정되지 않았으면 통과 (로컬 개발).
        # 배포에서는 check_startup 이 이미 막았다.
        if expected is None or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")

        if not _matches(header, expected):
            # 미들웨어가 던지는 예외는 FastAPI 의 핸들러를 거치지
            # 않는다. 라우팅 바깥이라 그대로 터진다. 응답을 직접
            # 돌려줘야 한다.
            #
            # WWW-Authenticate 가 있어야 브라우저가 자격 증명을 묻는다.
            return JSONResponse(
                {"detail": "Unauthorized"},
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": REALM},
            )

        return await call_next(request)


class ReadOnlyMiddleware(BaseHTTPMiddleware):
    """공개 데모에서 쓰기를 막는다.

    메서드로만 판단한다. 경로 목록을 관리하면 새 라우터가 생길
    때마다 빠뜨리게 되고, 빠뜨린 쪽이 열린 채로 남는다.
    """

    async def dispatch(self, request: Request, call_next):
        if is_read_only() and request.method in WRITE_METHODS:
            return JSONResponse(
                {
                    "detail": (
                        "이 배포본은 구경용입니다. 데이터를 바꿀 수 "
                        "없습니다."
                    )
                },
                status_code=status.HTTP_403_FORBIDDEN,
            )

        return await call_next(request)


def _matches(header: str, expected: tuple[str, str]) -> bool:
    import base64
    import binascii

    scheme, _, encoded = header.partition(" ")

    if scheme.lower() != "basic" or not encoded:
        return False

    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False

    user, _, password = decoded.partition(":")

    # 타이밍 공격을 피하려고 둘 다 상수 시간으로 비교한다.
    # 하나라도 먼저 끊으면 사용자명 존재 여부가 새어 나간다.
    #
    # 바이트로 비교하는 이유: compare_digest 는 비-ASCII 문자열을
    # 받으면 TypeError 를 던진다. 미들웨어 안에서 터지므로 401 이
    # 아니라 500 이 나가고, 한글 비밀번호를 쓴 사람은 자기 배포본에
    # 영영 못 들어간다.
    user_ok = secrets.compare_digest(
        user.encode("utf-8"), expected[0].encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        password.encode("utf-8"), expected[1].encode("utf-8")
    )

    return user_ok and password_ok
