"""Career OS 호출 — scripts/careeros 의 도구들이 같이 쓴다.

비밀번호는 실행할 때 getpass 로 묻는다. 파일 · 명령 기록에 남기지 않는다.

  BASE         기본은 배포본. 로컬은 BASE=http://localhost:8130 (인증 안 묻는다)
  CAREER_USER  아이디. 안 주면 묻는다 — 저장소에 아이디를 박아두지 않기 위해서다.
               묻는 입력도 화면에 안 보이게 받는다 (비밀번호를 잘못 넣어도 안 남는다).
               매번 묻는 게 번거로우면 `export CAREER_USER=...` 로 고정한다.
"""

import base64
import getpass
import json
import os
import sys
import urllib.error
import urllib.request


BASE = os.environ.get(
    "BASE", "https://career-os-real-production.up.railway.app"
).rstrip("/")
LOCAL = BASE.startswith(("http://localhost", "http://127.0.0.1"))


class Api:
    def __init__(self):
        self.header = None
        if LOCAL:
            return

        # 아이디도 getpass 로 받는다 — input() 은 화면에 그대로 찍힌다.
        # 비밀번호를 아이디 칸에 잘못 넣으면 터미널 기록에 평문으로 남는다 (실제로 났다).
        user = os.environ.get("CAREER_USER") or getpass.getpass("Career OS 아이디: ")
        password = getpass.getpass("Career OS 비밀번호: ")
        user = user.strip()
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.header = f"Basic {token}"

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(BASE + path, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if self.header:
            request.add_header("Authorization", self.header)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode()
                return response.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as error:
            raw = error.read().decode(errors="replace")
            try:
                detail = json.loads(raw).get("detail", raw)
            except (ValueError, AttributeError):
                detail = raw
            return error.code, detail
        except urllib.error.URLError as error:
            return 0, str(error.reason)

    def get(self, path):
        status, body = self.call("GET", path)
        if status == 401:
            sys.exit("비밀번호 또는 아이디가 맞지 않아요.")
        if status != 200:
            sys.exit(f"{path} 를 읽지 못했어요 (HTTP {status}): {body}")
        return body


def norm(text) -> str:
    return "".join(str(text or "").split()).lower()
