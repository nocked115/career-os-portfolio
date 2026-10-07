#!/usr/bin/env bash
#
# Career OS 를 이 노트북에서 띄운다. 배포본과 같은 모양 — 화면과 API 가
# 한 주소에 같이 있다. http://localhost:8000
#
#   bash scripts/local.sh
#
# Railway Trial 이 끝나면 여기가 원본이 된다. 배포본 데이터를 먼저
# 가져오려면 export 받아서 import 한다:
#
#   cd scripts/careeros && python3 export_production.py   # 배포본 → 파일
#   cd scripts && python3 careeros/import_local.py <파일>  # 파일 → 이 노트북
#
# 로컬에는 비밀번호가 없다. CAREER_OS_AUTH_* 를 안 주면 auth 가 꺼진다
# (backend/app/auth.py). 이 노트북 밖에서는 안 열린다 — 127.0.0.1 에만 묶는다.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

PORT="${PORT:-8000}"

# --- 0. 그 포트를 이미 누가 쓰고 있나 ---
# 터미널 두 개에서 띄우면 뒤엣것이 "address already in use" 로 죽는다.
# 그 메시지만 보고는 "이미 떠 있다" 는 걸 알기 어렵다.
if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  OWNER="$(lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN -t | head -1)"
  echo "▸ ${PORT} 번은 이미 쓰이고 있어요 (프로세스 ${OWNER})."
  if curl -fsS --max-time 3 "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
    echo "  Career OS 가 이미 떠 있습니다 — http://localhost:${PORT}"
    echo "  새로 띄우려면 먼저 멈추세요:  kill ${OWNER}"
  else
    echo "  다른 프로그램입니다. 다른 포트로 띄우려면:  PORT=8001 bash scripts/local.sh"
  fi
  exit 1
fi

# --- 1. 파이썬 환경 ---
if [ ! -x backend/.venv/bin/python ]; then
  echo "▸ 파이썬 환경을 만드는 중…"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install --quiet --upgrade pip
fi

# 로그인할 때 자동으로 띄우는 경우(scripts/autostart.sh)에는 건너뛴다.
# 매번 pip · npm 을 돌리면 로그인이 느려지고, 네트워크가 아직 안 올라온
# 상태에서 설치를 시도하다 실패한다.
if [ "${CAREER_OS_SKIP_DEPS:-0}" = "1" ]; then
  echo "▸ 라이브러리 확인은 건너뜁니다 (CAREER_OS_SKIP_DEPS=1)."
else
  echo "▸ 라이브러리 확인…"
  backend/.venv/bin/pip install --quiet -r backend/requirements.txt
fi

# --- 2. 화면 빌드 ---
# 배포본과 같은 자리(backend/static)에 둔다. main.py 가 거기서 찾는다.
# 소스가 빌드보다 새로우면 다시 빌드한다 — 안 그러면 고친 화면이 안 나온다.
NEED_BUILD=0
if [ ! -f backend/static/index.html ]; then
  NEED_BUILD=1
elif [ -n "$(find frontend/src frontend/index.html -newer backend/static/index.html 2>/dev/null | head -1)" ]; then
  NEED_BUILD=1
fi

if [ "$NEED_BUILD" = "1" ]; then
  echo "▸ 화면을 빌드하는 중…"
  if [ "${CAREER_OS_SKIP_DEPS:-0}" = "1" ]; then
    ( cd frontend && VITE_API_BASE_URL="" npm run build )
  else
    ( cd frontend && npm install --silent && VITE_API_BASE_URL="" npm run build )
  fi
  rm -rf backend/static
  cp -R frontend/dist backend/static
else
  echo "▸ 화면은 이미 최신이에요."
fi

# --- 3. 스키마 ---
# 스키마는 Alembic 이 소유한다. 배포본 CMD 와 같은 줄이다.
echo "▸ 데이터베이스 스키마를 맞추는 중…"
( cd backend && CAREER_OS_DATABASE_URL="sqlite:///./career_os.db" .venv/bin/alembic upgrade head )

# --- 4. 띄운다 ---
echo
echo "▸ http://localhost:${PORT} — 멈추려면 Ctrl+C"
echo "  데이터 파일: ${ROOT}/backend/career_os.db"
echo
cd backend
exec env CAREER_OS_DATABASE_URL="sqlite:///./career_os.db" \
     .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
