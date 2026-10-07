"""오늘 계획에 무엇이 어떤 순서로 들어 있는지 본다. 읽기 전용 — 아무것도 바꾸지 않는다.

  python3 check_today_plan.py

마감을 옮겼는데도 화면이 그대로로 보일 때 쓴다. 계획은 `planned` 상태만 다시 짜므로
(today.py generate_plan), 이미 시작했거나 끝낸 줄은 남아서 자리를 차지한다.
"""

from career_api import Api

api = Api()

plan = api.get("/today/plan")

print(f"오늘 {plan.get('date')} · 강도 {plan.get('intensity')}({plan.get('intensity_label')})")
print(f"예산 {plan.get('available_minutes')}분 · 계획 {plan.get('planned_minutes')}분 "
      f"· 남음 {plan.get('remaining_minutes')}분")
print(f"할 일 {plan.get('total_tasks')}개 (끝낸 것 {plan.get('done_tasks')}개)\n")

for t in plan.get("tasks", []):
    mark = {"done": "✅", "skipped": "⏭ ", "planned": "  "}.get(t.get("status"), "▶ ")
    print(f"{mark} {t.get('position')}. {(t.get('title') or '')[:46]:48} "
          f"{t.get('minutes')}분 · {t.get('status')} · {t.get('area')}")
    if t.get("reason"):
        print(f"      이유: {t['reason'][:74]}")
    if t.get("learning_step_id"):
        print(f"      learning_step_id {t['learning_step_id']}")

# 루틴이 맡은 경로는 "마감 있는 학습" 후보에서 통째로 빠진다 (today.py _due_learning_candidates).
# 그래서 루틴에 걸린 경로의 단계는 마감이 코앞이어도 계획에 안 올라온다.
print("루틴 (계획과 별도로 시간을 먼저 떼어 간다):")
for r in plan.get("routines", []) or []:
    print(f"  · {str(r.get('title') or r.get('name') or r)[:50]:52} {r.get('minutes') or ''}")
if not plan.get("routines"):
    print("  (없음)")

routines = api.get("/routines")
routines = routines if isinstance(routines, list) else routines.get("routines", [])
bound = [r for r in routines if r.get("learning_path_id")]
print(f"\n학습 경로에 걸린 루틴 {len(bound)}개 — 걸린 경로의 단계는 마감 학습 후보에서 빠진다")
for r in bound:
    print(f"  · {str(r.get('title') or r.get('name'))[:40]:42} → 경로 #{r.get('learning_path_id')}"
          f" · active {r.get('active')}")

outdated = plan.get("outdated")
if outdated:
    print(f"\n⚠ 계획이 낡았다고 표시됨: {outdated}")

# 사흘 넘게 밀린 것 — 계획에 안 올라가고 여기서 "안 할 건가요?" 를 묻는다.
# 이걸 안 찍으면 밀린 일이 아무 데도 없는 것처럼 보인다 (실제로 그렇게 헷갈렸다).
stale = plan.get("stale") or []
print(f"\n밀려서 계획에서 빠진 것 {len(stale)}개 (화면에선 \"이건 안 할 건가요?\" 칸):")
for t in stale:
    print(f"  · {(t.get('title') or '')[:52]:54} {t.get('days_carried')}일째 · {t.get('minutes')}분")
if not stale:
    print("  (없음)")

# 마감이 지난 학습 단계 — 마감 목록은 앞으로 올 것만 보여주므로 여기서 따로 센다.
from datetime import date
today = date.fromisoformat(str(plan.get("date")))
overdue = []
paths = api.get("/learning-paths")
paths = paths if isinstance(paths, list) else paths.get("paths", [])
for p in paths:
    steps = api.get(f"/learning-steps?learning_path_id={p['id']}")
    steps = steps if isinstance(steps, list) else steps.get("steps", [])
    for st in steps:
        due = st.get("due_date")
        if not due or st.get("status") == "completed":
            continue
        if date.fromisoformat(str(due)) < today:
            overdue.append((due, p.get("title"), st))

print(f"\n마감이 지난 학습 단계 {len(overdue)}개 (마감 목록엔 안 나온다):")
for due, path_title, st in sorted(overdue):
    body = api.get(f"/learning-steps/{st['id']}/checklist")
    sections = body.get("sections", [])
    total = sum(len(sec.get("items", [])) for sec in sections)
    done = sum(1 for sec in sections for i in sec.get("items", []) if i.get("done"))
    print(f"  {due}  D+{(today - date.fromisoformat(str(due))).days:<3} "
          f"{(path_title or '')[:22]:24} {(st.get('title') or '')[:30]:32} "
          f"{st.get('status'):12} 체크 {done}/{total}")
if not overdue:
    print("  (없음)")

print("\n마감 목록 (계획에 자리가 없어도 여기엔 뜬다):")
for d in plan.get("deadlines", [])[:10]:
    title = str(d.get("title") or d)[:46]
    when = d.get("due_date") or d.get("date") or ""
    left = d.get("days_left")
    flag = " ⚡" if d.get("urgent") else ""
    print(f"  {str(when):12} D-{left if left is not None else '?':<4} {title}{flag}")
