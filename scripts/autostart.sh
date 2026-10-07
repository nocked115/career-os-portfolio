#!/usr/bin/env bash
#
# 로그인할 때 Career OS 를 저절로 띄운다. 터미널을 안 열어도 된다.
#
#   bash scripts/autostart.sh on      켜기
#   bash scripts/autostart.sh off     끄기 (바로 멈춘다)
#   bash scripts/autostart.sh status  지금 어떤 상태인지
#
# macOS 의 LaunchAgent 를 쓴다. 내 계정에만 걸리는 것이라 관리자 비밀번호가
# 필요 없고, off 한 번으로 흔적 없이 지워진다. 시스템 설정은 안 건드린다.
#
# 켜도 달라지는 건 "터미널을 열어둘 필요가 없다" 뿐이다. 서버는 여전히
# 127.0.0.1 에만 묶여서 이 노트북 밖에서는 열리지 않는다.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

LABEL="com.career-os.local"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/career-os.log"
PORT="${PORT:-8000}"

say() { printf '%s\n' "$*"; }

running() {
  curl -fsS --max-time 3 "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1
}

case "${1:-status}" in

on)
  mkdir -p "$HOME/Library/LaunchAgents" "$(dirname "$LOG")"

  # 로그인 때는 pip · npm 을 돌리지 않는다. 느려지고, 네트워크가 아직
  # 안 올라온 상태에서 설치를 시도하다 실패한다. 라이브러리를 새로
  # 받아야 할 때는 터미널에서 scripts/local.sh 를 한 번 돌리면 된다.
  cat > "$PLIST" <<PLIST_END
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$ROOT/scripts/local.sh</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>CAREER_OS_SKIP_DEPS</key>
    <string>1</string>
    <key>PORT</key>
    <string>$PORT</string>
    <key>PATH</key>
    <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>

  <key>WorkingDirectory</key>
  <string>$ROOT</string>

  <key>RunAtLoad</key>
  <true/>

  <!-- 꺼지면 다시 띄운다. 단, 1초 만에 죽는 걸 무한 반복하지 않게 10초 둔다. -->
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>

  <key>StandardOutPath</key>
  <string>$LOG</string>
  <key>StandardErrorPath</key>
  <string>$LOG</string>
</dict>
</plist>
PLIST_END

  # 이미 올라가 있으면 내리고 다시 올린다 (설정이 바뀌었을 수 있다).
  launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$UID" "$PLIST"

  # 켰다고 말하기 전에 **실제로 떴는지** 본다.
  #
  # macOS 는 ~/Documents · ~/Desktop · ~/Downloads 를 보호한다(TCC).
  # 로그인 때 뜨는 프로세스는 거기 있는 파일을 못 읽어서 조용히 실패하고,
  # KeepAlive 가 10초마다 다시 시도하며 로그만 쌓는다. 실제로 그랬다:
  #   /bin/bash: .../scripts/local.sh: Operation not permitted
  say "▸ 올렸어요. 뜨는지 확인하는 중…"

  for _ in $(seq 1 20); do
    running && break
    sleep 2
  done

  if running; then
    say "▸ 켰어요. 다음 로그인부터 저절로 뜹니다 — http://localhost:${PORT}"
    say "  로그: $LOG"
    say "  끄려면:  bash scripts/autostart.sh off"
    exit 0
  fi

  # 못 떴다. 되돌린다 — 10초마다 실패를 반복하는 것을 남겨두지 않는다.
  launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"

  say ""
  say "▸ 안 떴어요. 되돌렸습니다 (자동 실행은 꺼진 상태입니다)."

  if grep -q "Operation not permitted" "$LOG" 2>/dev/null; then
    say ""
    say "  까닭: macOS 가 ~/Documents 안의 파일을 보호하고 있어서,"
    say "        로그인할 때 뜨는 프로그램은 이 폴더를 못 읽습니다."
    say "        (관리자 권한으로 풀 수는 있지만 보안 설정이라 권하지 않습니다.)"
    say ""
    say "  대신 이쪽이 더 간단해요 — 바탕화면에서 두 번 누르기:"
    say ""
    say "        open '$ROOT/scripts'"
    say "        거기 'Career OS 켜기.command' 를 더블클릭하세요."
    say ""
    say "  로그인할 때 저절로 뜨게 하려면 그 파일을"
    say "  시스템 설정 → 일반 → 로그인 항목 → '+' 에 추가하면 됩니다."
    say "  (처음 한 번 '문서 폴더 접근' 을 물으면 허용하세요.)"
    say "  빼는 것도 같은 자리에서 '−' 한 번입니다."
  else
    say ""
    say "  로그를 보세요: $LOG"
    tail -10 "$LOG" | sed 's/^/    /'
  fi

  exit 1
  ;;

off)
  # bootout 은 등록을 지우면서 돌고 있는 것도 같이 멈춘다.
  if launchctl bootout "gui/$UID/$LABEL" 2>/dev/null; then
    say "▸ 껐어요. 돌고 있던 것도 멈췄습니다."
  else
    say "▸ 켜져 있지 않았어요."
  fi

  rm -f "$PLIST"

  say "  이제 쓰려면 터미널에서:  bash scripts/local.sh"
  ;;

status)
  if [ -f "$PLIST" ]; then
    say "자동 실행: 켜짐"
  else
    say "자동 실행: 꺼짐  (켜려면 bash scripts/autostart.sh on)"
  fi

  if running; then
    say "서버      : 돌고 있음 — http://localhost:${PORT}"
  else
    say "서버      : 안 돌고 있음"
  fi

  if [ -f "$LOG" ]; then
    say ""
    say "로그 마지막 5줄 ($LOG):"
    tail -5 "$LOG" | sed 's/^/  /'
  fi
  ;;

*)
  say "쓰는 법:  bash scripts/autostart.sh [on|off|status]"
  exit 1
  ;;
esac
