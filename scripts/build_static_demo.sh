#!/usr/bin/env bash
# GitHub Pages 용 정적 데모를 만든다 — 서버 없이 열리는 읽기 전용 Career OS.
#
#   bash scripts/build_static_demo.sh            # → static-demo/ 폴더
#
# 1. 임시 SQLite 에 마이그레이션 → 가상 데모 데이터 → 화면이 읽는 GET 응답을 한 파일로 녹화
# 2. 앱을 정적 데모 모드(VITE_STATIC_DEMO=1)로, 상대 경로(--base=./)로 빌드
# 3. 녹화 파일을 빌드 결과 옆에 둔다
#
# 진짜 데이터 · 인증키는 쓰지 않는다. 임시 DB 만 쓰고, 외부 API 키는 녹화 전에 지운다.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/static-demo"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

DEMO_DATE="$(date +%Y-%m-%d)"

echo "1/3 데모 데이터 녹화 (임시 DB)"
cd "$ROOT/backend"
export CAREER_OS_DATABASE_URL="sqlite:///$TMP/demo.db"
unset WORK24_API_KEY SARAMIN_API_KEY DATA_GO_KR_SERVICE_KEY || true
.venv/bin/alembic upgrade head > /dev/null
.venv/bin/python -m app.static_demo --out "$TMP/demo-data.json"

echo "2/3 정적 빌드"
cd "$ROOT/frontend"
rm -rf "$OUT"
VITE_STATIC_DEMO=1 VITE_DEMO_DATE="$DEMO_DATE" npx vite build --base=./ --outDir "$OUT" --emptyOutDir > /dev/null

echo "3/3 녹화 파일 넣기"
cp "$TMP/demo-data.json" "$OUT/demo-data.json"
# GitHub Pages 가 _ 로 시작하는 파일을 숨기지 않게.
touch "$OUT/.nojekyll"

echo "완료: $OUT ($(du -sh "$OUT" | cut -f1), 데모 기준일 $DEMO_DATE)"
