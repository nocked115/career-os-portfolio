"""학습 단계의 마감일을 바꾼다. 한 경로의 여러 단계를 한 번에 옮길 수 있다.

  python3 set_due.py <경로 표식> <단계 표식>=<YYYY-MM-DD|none> [...] [--apply]

  python3 set_due.py Tave 2주차=2026-10-06 --apply
  python3 set_due.py 생성형 복습=2026-10-05 "3주차 2차시=2026-10-07" 4주차=2026-10-12 --apply
  python3 set_due.py Tave 1주차=none --apply        # 마감 없애기 (놓아두기)

  옛 형태(공백 셋)도 받는다: set_due.py Tave 2주차 2026-10-06

밀린 수업을 순서대로 다시 세울 때 한 번에 하라고 여러 개를 받는다 —
하나씩 하면 그 사이 계획이 중간 상태로 세워지고, 비밀번호도 매번 묻는다.

표식은 제목에 든 말이면 된다. **정확히 하나만 걸려야** 바꾼다 —
여럿이 걸리면 무엇을 바꿀지 사람이 정해야 하므로 멈춘다.
("추천시스템" 은 수업 경로와 심화 경로 둘 다에 들어 있어 실제로 멈춘 적이 있다.)
"""

import sys
from datetime import date

from career_api import Api

args = [a for a in sys.argv[1:] if not a.startswith("--")]
apply = "--apply" in sys.argv

if len(args) < 2:
    sys.exit(__doc__)

path_mark = args[0]

# 옛 형태(표식 날짜)와 새 형태(표식=날짜)를 둘 다 받는다.
if len(args) == 3 and "=" not in args[1]:
    pairs = [(args[1], args[2])]
else:
    pairs = []
    for raw in args[1:]:
        if "=" not in raw:
            sys.exit(f"'단계표식=날짜' 형태여야 해요: {raw}")
        mark, _, want = raw.partition("=")
        pairs.append((mark.strip(), want.strip()))

changes = []
for mark, want in pairs:
    due = None if want.lower() in ("none", "없음", "-") else want
    if due:
        try:
            date.fromisoformat(due)
        except ValueError:
            sys.exit(f"날짜가 YYYY-MM-DD 가 아니에요: {want}")
    changes.append((mark, due))

api = Api()

paths = api.get("/learning-paths")
paths = paths if isinstance(paths, list) else paths.get("paths", [])
hits = [p for p in paths if path_mark in (p.get("title") or "")]
if len(hits) != 1:
    sys.exit(f"'{path_mark}' 경로가 {len(hits)}개예요: "
             + ", ".join(f"#{p['id']} {p.get('title')}" for p in hits))
path = hits[0]

steps = api.get(f"/learning-steps?learning_path_id={path['id']}")
steps = steps if isinstance(steps, list) else steps.get("steps", [])

print(f"경로 #{path['id']} {path['title']}\n")

todo = []
for mark, due in changes:
    found = [s for s in steps if mark in (s.get("title") or "")]
    if len(found) != 1:
        sys.exit(f"'{mark}' 단계가 {len(found)}개예요: "
                 + ", ".join(f"#{s['id']} {s.get('title')}" for s in found))
    step = found[0]
    now = str(step.get("due_date") or "없음")
    after = due or "없음"
    mark_same = "  (그대로)" if now == after else ""
    print(f"  #{step['id']} {step['title'][:42]:44} {now}  →  {after}{mark_same}")
    if now != after:
        todo.append((step, due))

if not todo:
    sys.exit("\n바꿀 것이 없어요.")

if not apply:
    print(f"\n{len(todo)}개를 바꿉니다. 지금은 보여주기만 했어요 — --apply 를 붙이세요.")
    sys.exit(0)

for step, due in todo:
    status, saved = api.call("PATCH", f"/learning-steps/{step['id']}", {"due_date": due})
    if status != 200:
        sys.exit(f"'{step['title'][:30]}' 을(를) 바꾸지 못했어요 (HTTP {status}): {saved}")
    print(f"✅ {step['title'][:42]:44} 마감 {saved.get('due_date') or '없음'}")

plan = api.get("/today/plan")
minutes = plan.get("available_minutes") or 120
code, _ = api.call("POST", f"/today/plan?available_minutes={minutes}"
                           f"&intensity={plan.get('intensity','normal')}")
print(f"오늘 계획 다시 세우기 → HTTP {code}")

after_steps = api.get(f"/learning-steps?learning_path_id={path['id']}")
after_steps = after_steps if isinstance(after_steps, list) else after_steps.get("steps", [])
print(f"\n{path['title']} 단계 (마감순):")
for s in sorted(after_steps, key=lambda x: str(x.get("due_date") or "9999")):
    print(f"  {str(s.get('due_date') or '마감없음'):12} {(s.get('title') or '')[:46]}")
