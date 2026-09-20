"""공고 주소 하나를 받아 본문을 가져온다 — 사람이 보고 있는 그 공고 한 건만.

수집 순서는 셋이다 (DECISIONS: 공고 수집).
  ① 공식 API            고용24 · 사람인(승인 시)
  ② 허용된 공개 소스     robots 가 막지 않는 기업 채용 페이지 · 공공기관
  ③ 주소 넣기 · 붙여넣기  나머지 전부

이 모듈은 ③ 이다. 목록을 훑지 않는다. 사람이 고른 주소 하나를 한 번 가져온다.

지키는 것
  - robots.txt 를 먼저 읽고, 우리 이름으로 막혀 있으면 가져오지 않는다.
    막혔다고 우회하지 않는다 — 그 자리에서 "본문을 복사해 붙여넣으세요" 로 넘긴다.
  - http(s) 만. 사내망 · 로컬 주소(127.x · 10.x · 192.168.x · localhost)는 막는다.
    서버가 사용자가 준 주소로 요청하는 구조라, 막지 않으면 내부망을 긁는 통로가 된다.
  - 크기 · 시간 상한을 둔다. 받은 것은 글자만 남기고 버린다(스크립트 · 스타일 제거).
"""

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

# 우리가 누구인지 밝힌다. 브라우저인 척하지 않는다.
USER_AGENT = "CareerOS/1.0 (personal job tracker; one page per request)"

TIMEOUT_SECONDS = 10
MAX_BYTES = 2_000_000

BLOCKED_HOST_WORDS = ("localhost", "metadata.google.internal")

SCRIPT_STYLE = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.I | re.S)
BREAKS = re.compile(r"</(p|div|li|tr|h[1-6]|section|article|br)\s*>|<br\s*/?>", re.I)
TAGS = re.compile(r"<[^>]+>")
SPACES = re.compile(r"[ \t\x0b\f\r]+")
BLANKS = re.compile(r"\n{3,}")


class ImportError_(Exception):
    """가져오지 못한 이유. 화면에 그대로 보인다."""


def _check_url(url: str, resolve: bool = True) -> urllib.parse.ParseResult:
    """주소가 바깥의 공개 주소인가. resolve 는 이름 조회 여부 — 테스트에서 가짜 열기를
    쓸 때만 끈다. 실제 경로(기본 열기)에서는 항상 조회한다."""
    parsed = urllib.parse.urlparse(url.strip())

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ImportError_("http 또는 https 로 시작하는 공고 주소를 넣어 주세요.")

    host = parsed.hostname.lower()

    if any(word in host for word in BLOCKED_HOST_WORDS):
        raise ImportError_("이 주소는 가져올 수 없어요.")

    try:
        ip_literal = ipaddress.ip_address(host)
    except ValueError:
        ip_literal = None

    if ip_literal is not None:
        if ip_literal.is_private or ip_literal.is_loopback or ip_literal.is_link_local:
            raise ImportError_("이 주소는 가져올 수 없어요.")
        return parsed

    if not resolve:
        return parsed

    try:
        for info in socket.getaddrinfo(host, None):
            address = ipaddress.ip_address(info[4][0])
            if address.is_private or address.is_loopback or address.is_link_local:
                raise ImportError_("이 주소는 가져올 수 없어요.")
    except socket.gaierror as error:
        raise ImportError_("주소를 찾지 못했어요. 오타가 없는지 확인해 주세요.") from error

    return parsed


def robots_allows(url: str, opener=None) -> bool:
    """robots.txt 가 우리 이름을 막지 않는가. 못 읽으면 막지 않은 것으로 본다."""
    parsed = urllib.parse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    parser = urllib.robotparser.RobotFileParser()

    try:
        raw = (opener or _open)(robots_url)
    except ImportError_:
        return True

    parser.parse(raw.splitlines())

    return parser.can_fetch(USER_AGENT, url)


def _open(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            kind = (response.headers.get_content_type() or "").lower()

            if kind not in ("text/html", "text/plain", "application/xhtml+xml"):
                raise ImportError_(f"글이 아니라 {kind or '알 수 없는 형식'} 이라 읽지 못했어요.")

            charset = response.headers.get_content_charset() or "utf-8"
            return response.read(MAX_BYTES).decode(charset, errors="replace")
    except urllib.error.HTTPError as error:
        raise ImportError_(f"공고 페이지가 {error.code} 로 답했어요. 본문을 복사해 붙여넣어 주세요.") from error
    except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
        raise ImportError_("공고 페이지를 열지 못했어요. 본문을 복사해 붙여넣어 주세요.") from error


def to_text(html: str) -> str:
    """태그를 걷고 글자만 남긴다. 줄 구분은 살린다 — 파서가 줄 단위로 읽는다."""
    text = SCRIPT_STYLE.sub(" ", html)
    text = BREAKS.sub("\n", text)
    text = TAGS.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&")
        .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    )
    text = SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())

    return BLANKS.sub("\n\n", text).strip()


def fetch_posting(url: str, opener=None) -> str:
    """공고 한 건의 본문 글. 막혀 있으면 이유를 들고 멈춘다."""
    _check_url(url, resolve=opener is None)
    opener = opener or _open

    if not robots_allows(url, opener):
        raise ImportError_(
            "이 사이트는 자동 접근을 robots.txt 로 막아 뒀어요. "
            "공고 본문을 복사해 아래에 붙여넣어 주세요."
        )

    text = to_text(opener(url))

    if len(text) < 100:
        raise ImportError_(
            "페이지에서 글을 거의 찾지 못했어요(화면을 그려야 보이는 공고일 수 있어요). "
            "본문을 복사해 붙여넣어 주세요."
        )

    return text
