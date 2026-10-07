"""프로젝트 목록을 본다. 읽기 전용.

같은 프로젝트가 여러 줄로 들어가 있는지 보려고 만들었다.
프로젝트(/projects)와 학습 경로(/learning-paths)는 다른 것이라 이름이 겹쳐도
서로 모른다 — 둘 다 찍어서 나란히 본다.

  python3 check_projects.py
"""

from career_api import Api

api = Api()

rows = api.get("/projects")
rows = rows if isinstance(rows, list) else rows.get("projects", [])

print(f"프로젝트 {len(rows)}개  (/projects)\n")
for p in sorted(rows, key=lambda x: str(x.get("name"))):
    print(f"#{p['id']} {p.get('name')}")
    print(f"   상태 {p.get('status'):12} 용도 {p.get('purpose'):9} 진행 {p.get('progress_percent')}%"
          f" · 목표일 {p.get('target_date') or '없음'} · 하루 {p.get('daily_minutes')}분")
    if p.get("description"):
        print(f"   설명 {p['description'][:70]}")
    if p.get("why"):
        print(f"   왜   {p['why'][:70]}")
    links = [p.get("github_url"), p.get("demo_url")]
    links = [l for l in links if l]
    if links:
        print(f"   링크 {' · '.join(links)[:70]}")
    print()

paths = api.get("/learning-paths")
paths = paths if isinstance(paths, list) else paths.get("paths", [])
print(f"\n학습 경로 {len(paths)}개  (/learning-paths — 프로젝트와 다른 것)\n")
for p in paths:
    print(f"#{p['id']} {p.get('title')}")
    print(f"   갈래 {p.get('kind'):8} 상태 {p.get('status'):14} 목표일 {p.get('target_date') or '없음'}")

# 이름이 겹치는 것 찾기
print("\n\n이름이 겹치는 것 (프로젝트 ↔ 학습 경로):")
def squash(t):
    return "".join(str(t or "").split()).lower()

found = False
for pr in rows:
    for pa in paths:
        a, b = squash(pr.get("name")), squash(pa.get("title"))
        if a and b and (a in b or b in a):
            print(f"  프로젝트 #{pr['id']} {pr.get('name')}")
            print(f"  ↔ 경로   #{pa['id']} {pa.get('title')}")
            found = True
if not found:
    print("  (없음)")
