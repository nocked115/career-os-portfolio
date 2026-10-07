"""배포본 데이터를 통째로 내려받아 파일로 둔다. 읽기 전용 — 서버는 안 건드린다.

  python3 export_production.py

Railway Trial 이 2026-10-08 경 끝난다. 볼륨 안 SQLite 는 밖에서 못 만지므로
이 export 가 데이터를 빼는 **유일한 길**이다 (docs/DEPLOY.md 7장).

받은 파일은 나중에 로컬에 넣을 때 쓴다:
  POST /transfer/import?confirm=... (기존 데이터를 지우고 대체한다)
"""

import json
import os
import sys
from datetime import datetime

from career_api import Api

OUT_DIR = os.path.expanduser("~/Documents/career-os/backups")


def main():
    api = Api()

    print("배포본에서 내려받는 중…")
    data = api.get("/transfer/export")

    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    path = os.path.join(OUT_DIR, f"career-os-production-{stamp}.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    size = os.path.getsize(path)
    print(f"\n저장했어요 — {path}")
    print(f"  {size:,} 바이트")

    # 무엇이 들어왔는지 센다. 빈 파일을 백업이라고 믿지 않기 위해서다.
    # 줄은 최상위가 아니라 data["tables"] 안에 있다 — 최상위만 세면 늘 0 이 나온다.
    print(f"\n스키마 {data.get('schema_revision')} · 뜬 시각 {data.get('exported_at')}")
    tables = data.get("tables") or {}
    counted = 0
    print("\n담긴 것:")
    for name, rows in sorted(tables.items(), key=lambda kv: -(len(kv[1]) if isinstance(kv[1], list) else 0)):
        n = len(rows) if isinstance(rows, list) else 0
        counted += n
        if n:
            print(f"  {name:32} {n:>5}건")
    print(f"\n표 {len(tables)}개 · 합계 {counted:,}건")

    if counted == 0:
        sys.exit("⚠ 아무것도 안 들어왔어요. 백업으로 쓰면 안 됩니다.")


if __name__ == "__main__":
    main()
