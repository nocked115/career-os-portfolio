"""지원서 목록을 본다. 읽기 전용.

무엇이 어느 공고에 붙어 있는지, 자소서가 얼마나 채워졌는지, 이상한 것은 없는지 본다.

  python3 check_applications.py
"""

from collections import defaultdict

from career_api import Api

api = Api()

apps = api.get("/applications")
apps = apps if isinstance(apps, list) else apps.get("applications", [])

rows = api.get("/opportunities")
rows = rows if isinstance(rows, list) else rows.get("opportunities", [])
by_id = {r["id"]: r for r in rows}

questions = api.get("/cover-letter-questions")
questions = questions if isinstance(questions, list) else questions.get("questions", [])
by_app = defaultdict(list)
for q in questions:
    by_app[q.get("application_id")].append(q)

print(f"지원서 {len(apps)}건\n")

seen = defaultdict(list)
for a in sorted(apps, key=lambda x: str(x.get("applied_at") or ""), reverse=True):
    opportunity = by_id.get(a.get("opportunity_id"))
    mine = by_app.get(a["id"], [])

    letters = 0
    for q in mine:
        answers = api.get(f"/cover-letter-questions/{q['id']}/answers")
        answers = answers if isinstance(answers, list) else answers.get("answers", [])
        letters += sum(len(x.get("draft") or "") for x in answers)

    print(f"#{a['id']} {a.get('status')}"
          f" · 지원일 {str(a.get('applied_at') or '없음')[:10]}"
          f" · 마감 {str(a.get('deadline') or '없음')[:10]}")

    if opportunity is None:
        print(f"   ⚠ 공고 #{a.get('opportunity_id')} 를 못 찾음 (지워졌을 수 있음)")
    else:
        print(f"   공고 #{opportunity['id']} {opportunity.get('organization') or '(회사 없음)'}"
              f" — {(opportunity.get('title') or '')[:44]}")
        print(f"        공고 상태 {opportunity.get('status')}"
              + ("  ⚠ 지원했는데 공고가 applied 가 아님"
                 if a.get("status") == "applied" and opportunity.get("status") != "applied" else ""))
        seen[opportunity["id"]].append(a["id"])

    print(f"   자소서 {len(mine)}문항 · {letters}자")
    if a.get("notes"):
        print(f"   메모 {a['notes'].splitlines()[0][:66]}")
    print()

dupes = {k: v for k, v in seen.items() if len(v) > 1}
if dupes:
    print("⚠ 같은 공고에 지원서가 여럿:")
    for opportunity_id, ids in dupes.items():
        print(f"   공고 #{opportunity_id} ← 지원서 {', '.join('#' + str(i) for i in ids)}")
else:
    print("같은 공고에 겹치는 지원서 없음")

orphan = [q for q in questions if q.get("application_id") not in {a["id"] for a in apps}]
if orphan:
    print(f"\n⚠ 지원서가 없는 자소서 문항 {len(orphan)}개"
          f" (지원서 {sorted({q.get('application_id') for q in orphan})})")
