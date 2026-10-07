"""지금 살아 있는 공고 · 목표 직무 · 스킬 레벨을 한 번에 본다. 읽기 전용.

  python3 check_opportunities.py

어느 공고부터 쓸지 고르려고 만들었다. 매칭 점수 · 판정 · 마감 · 요구 스킬을 나란히 둔다.
자동으로 뺀 것(filtered_reason)도 따로 보여준다 — 규칙이 잘못 뺐을 수 있다.
"""

from datetime import date

from career_api import Api

api = Api()
today = date.today()

rows = api.get("/opportunities")
rows = rows if isinstance(rows, list) else rows.get("opportunities", [])


def days_left(row):
    due = row.get("deadline") or row.get("due_date") or row.get("apply_deadline")
    if not due:
        return None, ""
    text = str(due)[:10]
    try:
        return (date.fromisoformat(text) - today).days, text
    except ValueError:
        return None, text


live, filtered, done = [], [], []
for row in rows:
    if (row.get("filtered_reason") or "") and not row.get("keep_anyway"):
        filtered.append(row)
    elif row.get("status") in ("applied", "closed", "not_interested", "archived"):
        done.append(row)
    else:
        live.append(row)

print(f"공고 {len(rows)}건 — 검토 대상 {len(live)} · 자동 제외 {len(filtered)} · 끝난 것 {len(done)}\n")

print("=== 검토 대상 (마감 가까운 순) ===")
def key(row):
    n, _ = days_left(row)
    return (n if n is not None else 9999)

for row in sorted(live, key=key):
    n, text = days_left(row)
    tag = "마감없음" if n is None else (f"D+{-n} 지남" if n < 0 else f"D-{n}")
    score = row.get("match_score")
    print(f"\n[{tag:9}] {(row.get('title') or '')[:58]}")
    print(f"   {(row.get('organization') or row.get('company') or '')[:34]:36}"
          f" 상태 {row.get('status')} · 마감 {text or '—'}")
    print(f"   매칭 {score if score is not None else '—'} · 판정 {row.get('match_recommendation') or '—'}")
    skills = row.get("skills") or []
    if skills:
        print(f"   요구 스킬 {', '.join(str(s.get('name')) for s in skills)[:70]}")

print("\n\n=== 자동으로 뺀 것 (규칙이 잘못 뺐을 수 있다) ===")
for row in filtered[:12]:
    n, text = days_left(row)
    tag = "마감없음" if n is None else (f"D+{-n}" if n < 0 else f"D-{n}")
    print(f"  [{tag:7}] {(row.get('title') or '')[:52]}")
    print(f"            이유: {(row.get('filtered_reason') or '')[:64]}")
if not filtered:
    print("  (없음)")

print("\n\n=== 목표 직무 ===")
targets = api.get("/target-careers")
targets = targets if isinstance(targets, list) else targets.get("target_careers", [])
for t in targets:
    mark = "● 활성" if t.get("is_active") else "  "
    print(f"{mark} {t.get('title')} · 목표일 {t.get('target_date')}")
    print(f"     키워드: {(t.get('keywords') or '(없음)')[:76]}")
    if t.get("description"):
        print(f"     설명: {t['description'][:76]}")
if not targets:
    print("  (없음 — 목표 직무가 없으면 공고 인식·우선순위의 기준이 없다)")

print("\n\n=== 스킬 레벨 (0~4) ===")
skills = api.get("/skills")
skills = skills if isinstance(skills, list) else skills.get("skills", [])
for s in sorted(skills, key=lambda x: (-(x.get("level") or 0), str(x.get("name")))):
    print(f"  L{s.get('level')} {(s.get('name') or '')[:30]:32} {s.get('category') or ''}")
