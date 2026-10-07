"""경로 하나의 단계 · 마감 · 체크 진행을 본다. 읽기 전용.

  python3 check_path.py Tave
  python3 check_path.py Tave --items   # 체크 항목까지 (단계를 쪼갤 때 쓴다)

제목에 그 말이 든 경로를 전부 보여준다.
"""

import sys

from career_api import Api

args = [a for a in sys.argv[1:] if not a.startswith("--")]
show_items = "--items" in sys.argv

if not args:
    sys.exit("찾을 말을 주세요 — 예: python3 check_path.py Tave")

needle = args[0].lower()
api = Api()

paths = api.get("/learning-paths")
paths = paths if isinstance(paths, list) else paths.get("paths", [])
hits = [p for p in paths if needle in (p.get("title") or "").lower()]

if not hits:
    sys.exit("그런 경로가 없어요. 지금 있는 경로: "
             + ", ".join(f"#{p['id']} {p.get('title')}" for p in paths))

for p in hits:
    print(f"경로 #{p['id']} {p['title']}")
    print(f"  상태 {p.get('status')} · 목표일 {p.get('target_date')}")

    steps = api.get(f"/learning-steps?learning_path_id={p['id']}")
    steps = steps if isinstance(steps, list) else steps.get("steps", [])
    for s in sorted(steps, key=lambda x: (str(x.get("due_date") or "9999"), x.get("position", 0))):
        body = api.get(f"/learning-steps/{s['id']}/checklist")
        sections = body.get("sections", [])
        total = sum(len(sec.get("items", [])) for sec in sections)
        done = sum(1 for sec in sections for i in sec.get("items", []) if i.get("done"))
        print(f"  - #{s['id']} {(s.get('title') or '')[:40]:42} 마감 {str(s.get('due_date')):12}"
              f" {s.get('status'):12} 체크 {done}/{total} · 예상 {s.get('estimated_minutes')}분")

        if show_items:
            for sec in sections:
                items = sec.get("items", [])
                note = (sec.get("note") or "").strip()
                if not items and not note:
                    continue
                print(f"      [{sec.get('title') or '묶음 없음'}] {len(items)}개")
                if note:
                    print(f"       > {note[:72]}")
                for i in items:
                    mark = "x" if i.get("done") else " "
                    print(f"       [{mark}] {(i.get('text') or '')[:68]}")
    print()
