"""정적 데모(GitHub Pages)용 응답 녹화.

서버 없이 열리는 데모를 만들려고, 가상 데모 데이터를 넣은 임시 DB 에서 화면이 읽는
GET 응답을 한 파일로 저장한다. 프런트는 VITE_STATIC_DEMO=1 로 빌드하면 서버 대신
이 파일을 읽는다 (frontend/src/api.js).

    CAREER_OS_DATABASE_URL=sqlite:///tmp/demo.db python -m app.static_demo --out demo-data.json

반드시 임시 DB 로만 돌린다 — scripts/build_static_demo.sh 가 그렇게 부른다.
진짜 데이터가 든 DB 를 가리키면 멈춘다.
"""

import json
import os
import sys
from calendar import monthrange
from datetime import date, timedelta

DATABASE_URL = os.environ.get("CAREER_OS_DATABASE_URL", "")


def _guard():
    if not DATABASE_URL.startswith("sqlite:///") or "career_os.db" in DATABASE_URL:
        sys.exit("임시 SQLite DB 로만 돌립니다. scripts/build_static_demo.sh 를 쓰세요.")


def _month_shift(day: date, months: int):
    index = day.year * 12 + day.month - 1 + months
    return index // 12, index % 12 + 1


def main():
    _guard()

    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "demo-data.json"

    from fastapi.testclient import TestClient

    from . import demo
    from .database import SessionLocal
    from .main import app

    # app.collector 가 임포트될 때 .env 를 읽는다. 녹화 중에 외부 API 를 부를 일은 없지만 키를 지워 둔다.
    for name in ("WORK24_API_KEY", "SARAMIN_API_KEY", "DATA_GO_KR_SERVICE_KEY"):
        os.environ.pop(name, None)

    db = SessionLocal()
    try:
        demo.seed(db, force=True)
    finally:
        db.close()

    client = TestClient(app)
    today = date.today()

    def ok(response, label):
        if response.status_code >= 300:
            print(f"  꾸미기 실패 {response.status_code}: {label} — {response.text[:120]}")
            return None
        return response.json()

    # ---------- 새 기능이 보이게 꾸미기 (전부 가상) ----------
    routine = ok(client.post("/routines", json={
        "title": "코딩테스트 (Lv.1)", "minutes": 30, "target_count": 3, "unit_label": "문제",
    }), "루틴")
    if routine:
        for offset, count in ((1, 3), (2, 3), (3, 2), (4, 3), (5, 3), (6, 3)):
            client.put(f"/routines/{routine['id']}/logs/{(today - timedelta(days=offset)).isoformat()}",
                       json={"count": count})

    paths = client.get("/learning-paths").json()
    if paths:
        created = ok(client.post(f"/learning-paths/{paths[0]['id']}/checklist-steps", json={
            "title": "주차 발표 — 논문 정독과 미니 구현",
            "due_date": (today + timedelta(days=3)).isoformat(),
            "estimated_minutes": 60,
            "sections": [
                {"title": "논문 정독", "note": "구조 중심으로", "items": [
                    {"text": "Abstract · Figure 1 을 한 문단으로 설명해 적기", "done": True},
                    {"text": "`contrastive loss` 수식을 손으로 따라 적기"},
                ]},
                {"title": "실습", "note": "핵심 메커니즘만 직접 구현", "items": [
                    {"text": "사전학습 모델로 데모 한 번 돌려 보기"},
                    {"text": "미니 학습 코드 작성 · 임베딩 시각화"},
                ]},
                {"title": "발표", "items": [{"text": "핵심 아이디어 + 한계점 정리"}]},
            ],
            "links": [{"text": "논문 원문", "url": "https://arxiv.org/"}],
        }), "체크리스트 단계")
        if created:
            client.post(f"/learning-steps/{created['step_id']}/start")

    ok(client.put(f"/analytics/review/reflection?year={today.year}&month={today.month}", json={
        "rating": 4, "went_well": "코딩테스트를 거의 매일 풀었다",
        "to_improve": "발표 준비를 전날 몰아서 했다", "next_focus": "프로젝트 MVP 먼저, 공부는 주 3회",
    }), "스스로 평가")

    ok(client.post("/opportunities", json={
        "opportunity_type": "job_event", "title": "2026 청년 채용박람회 (가상)", "source": "manual",
        "location": "가상컨벤션센터 1층",
        "description": "일시: 행사 당일 13:00 ~ 17:00\n장소: 가상컨벤션센터 1층\n내용: 현장면접 · 채용설명회 · 이력서 컨설팅\n출처: 데모",
        "deadline": f"{(today + timedelta(days=9)).isoformat()}T17:00:00",
    }), "채용 행사")
    ok(client.post("/opportunities", json={
        "opportunity_type": "competition", "title": "지난 데이터 경진대회 (가상)", "source": "manual",
        "organization": "가상데이터재단", "deadline": f"{(today - timedelta(days=5)).isoformat()}T23:59:00",
    }), "마감 지난 기회")

    ok(client.post("/certificates", json={
        "category": "job", "name": "SQLD", "detail": "SQL 개발자", "issuer": "가상 발급기관",
        "status": "held", "acquired_on": (today - timedelta(days=300)).isoformat(),
        "expires_on": (today + timedelta(days=150)).isoformat(),
    }), "자격증")

    day = client.get("/calendar/day").json()
    minutes = day.get("suggested_minutes") or 120
    ok(client.post(f"/today/plan?available_minutes={minutes}&intensity=normal"), "오늘 계획")

    # ---------- 녹화 ----------
    responses = {}
    missed = []

    def record(path):
        if path in responses:
            return responses[path]
        response = client.get(path)
        if response.status_code != 200:
            missed.append(f"{response.status_code} {path}")
            return None
        responses[path] = response.json()
        return responses[path]

    for path in [
        "/today", "/today/deadlines", "/today/intensities", "/profile", "/config", "/overview",
        "/analytics/evidence", "/analytics/learning-priority", "/applications", "/applications/board",
        "/calendar/week", "/calendar/blocks", "/calendar/day", "/certificates", "/experiences",
        "/experiences/usage", "/jobs", "/learning-paths", "/opportunities", "/opportunities/matches",
        "/opportunities/recommended?limit=3", "/portfolio-entries", "/projects", "/resources", "/routines",
        "/skills", "/target-careers", "/target-careers/active", "/library",
        "/library/selection?available_minutes=120",
        "/universe?available_minutes=120", "/weekly-plan?daily_available_minutes=120",
        f"/today/plan?available_minutes={minutes}&intensity=normal",
        f"/today/why?available_minutes={minutes}&intensity=normal",
        "/analytics/market-signals", "/analytics/market-signals?limit=6", "/analytics/review/trend?months=6",
    ]:
        record(path)

    # 정적 데모는 저장되지 않는다 — 화면이 쓰기 버튼을 알아서 막게.
    responses["/config"] = {"read_only": True, "static_demo": True}

    for months in (-2, -1, 0, 1):
        year, month = _month_shift(today, months)
        record(f"/calendar/month?year={year}&month={month}")
        if months <= 0:
            record(f"/analytics/review?year={year}&month={month}")
            record(f"/analytics/activity?year={year}&month={month}")

    first = today.replace(day=1) - timedelta(days=7)
    _, days_in_month = monthrange(today.year, today.month)
    last = today.replace(day=days_in_month) + timedelta(days=14)
    cursor = first
    while cursor <= last:
        record(f"/calendar/day?date={cursor.isoformat()}")
        cursor += timedelta(days=1)

    for path in responses.get("/learning-paths") or []:
        record(f"/learning-paths/{path['id']}")
        record(f"/learning-paths/{path['id']}/progress")
        for step in record(f"/learning-steps?learning_path_id={path['id']}") or []:
            record(f"/learning-steps/{step['id']}/session")
            record(f"/learning-steps/{step['id']}/checklist")
            record(f"/learning-steps/{step['id']}/handoff")
            record(f"/learning-steps/{step['id']}/selection?available_minutes={step.get('estimated_minutes') or 45}")

    for resource in responses.get("/resources") or []:
        record(f"/resources/{resource['id']}/segments")
    for skill in responses.get("/skills") or []:
        record(f"/skills/{skill['id']}/level-events")
    for project in responses.get("/projects") or []:
        record(f"/projects/{project['id']}/eta")
        record(f"/projects/{project['id']}/evidence")

    matches = responses.get("/opportunities/matches") or {}
    for match in (matches.get("matches") if isinstance(matches, dict) else matches) or []:
        record(f"/opportunities/{match['opportunity_id']}/map")

    for application in responses.get("/applications") or []:
        record(f"/applications/{application['id']}/analysis")
        record(f"/applications/{application['id']}/experiences")
        record(f"/applications/{application['id']}/transitions")
        for question in record(f"/cover-letter-questions?application_id={application['id']}") or []:
            record(f"/cover-letter-questions/{question['id']}/answers")
            record(f"/cover-letter-questions/{question['id']}/outline")

    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"generated_at": today.isoformat(), "responses": responses}, handle,
                  ensure_ascii=False, default=str)

    print(f"  녹화 {len(responses)}개 · 건너뜀 {len(missed)}개")
    for line in missed[:10]:
        print(f"    - {line}")


if __name__ == "__main__":
    main()
