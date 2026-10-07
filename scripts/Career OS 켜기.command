#!/bin/bash
#
# 두 번 눌러서 Career OS 를 켠다. 터미널에 뭘 치지 않아도 된다.
#
# 로그인할 때 저절로 뜨게 하려면 이 파일을
#   시스템 설정 → 일반 → 로그인 항목 → "+"
# 에 추가한다. 빼는 것도 같은 자리에서 "−" 한 번이다.
#
# (launchd 로 띄우는 길도 있지만 — scripts/autostart.sh — macOS 가
#  ~/Documents 를 보호해서 로그인 때 뜨는 프로세스는 이 폴더를 못 읽는다.
#  그걸 풀려면 보안 설정을 건드려야 해서, 이쪽이 낫다.)

cd "$(dirname "$0")/.." || exit 1

# 이미 떠 있으면 새로 띄우지 않고 브라우저만 연다.
if curl -fsS --max-time 3 "http://127.0.0.1:${PORT:-8000}/healthz" >/dev/null 2>&1; then
  echo "이미 켜져 있어요 — http://localhost:${PORT:-8000}"
  open "http://localhost:${PORT:-8000}"
  echo
  echo "이 창은 닫아도 됩니다."
  exit 0
fi

echo "Career OS 를 켜는 중이에요. 잠시만요…"
echo

# 뜨면 브라우저를 연다. 서버가 준비될 때까지 기다렸다가 연다.
(
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 2 "http://127.0.0.1:${PORT:-8000}/healthz" >/dev/null 2>&1; then
      open "http://localhost:${PORT:-8000}"
      exit 0
    fi
    sleep 2
  done
) &

echo "※ 이 창을 닫으면 Career OS 도 꺼집니다. 열어 두세요."
echo "   끄려면 이 창에서 Ctrl+C."
echo

exec bash scripts/local.sh
