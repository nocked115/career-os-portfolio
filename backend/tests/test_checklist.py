"""학습 단계 체크리스트 — 붙여넣기 읽기, 저장, 체크, 오늘 계획에 보이기."""

from datetime import date

from app import models
from app.services import checklist_parser
from app.services import today as today_service


ARTIFACT = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<title>2주차 체크리스트 — Past vs. Now</title>
<style>.task{cursor:pointer}</style></head>
<body><div class="page">
<header>
  <p class="eyebrow">Past vs. Now · 2주차</p>
  <h1>인기 기반 &amp; 내용 기반 추천</h1>
  <div class="links">
    <p class="links-title">이번 주 자료</p>
    <a href="https://example.com/notion" target="_blank">📄 Notion — W01B 수업 자료</a>
    <a href="javascript:alert(1)">나쁜 링크</a>
  </div>
</header>
<section class="track">
  <div class="track-head"><h2>1. 수업 실습 — MovieLens 100K</h2><span data-count></span></div>
  <ul class="tasks">
    <li><div class="task"><div class="box"><svg viewBox="0 0 24 24"><path d="M4 12"/></svg></div>
      <span class="task-text"><code>u.user</code> / <code>u.item</code> 로드</span></div></li>
    <li><div class="task"><span class="task-text">Gradio 앱 실행</span></div></li>
  </ul>
</section>
<section class="track">
  <div class="track-head"><h2>2. 프로젝트 자력 구현 — Kindle_Store</h2></div>
  <p class="track-note">numpy / pandas 만 — 완성 코드 대신 받지 않는 구간</p>
  <ul class="tasks">
    <li><div class="task"><span class="task-text">TF-IDF 벡터화</span></div></li>
  </ul>
</section>
<div class="reset"><button id="resetBtn">체크 초기화</button></div>
</div>
<script>const tasks = document.querySelectorAll('.task');</script>
</body></html>"""


def test_an_artifact_page_becomes_sections_items_and_links():
    parsed = checklist_parser.parse_checklist(ARTIFACT)

    assert parsed["format"] == "html"
    assert parsed["title"] == "인기 기반 & 내용 기반 추천"
    assert [s["title"] for s in parsed["sections"]] == [
        "1. 수업 실습 — MovieLens 100K",
        "2. 프로젝트 자력 구현 — Kindle_Store",
    ]
    assert parsed["sections"][0]["items"][0]["text"] == "`u.user` / `u.item` 로드"
    assert parsed["sections"][1]["note"] == "numpy / pandas 만 — 완성 코드 대신 받지 않는 구간"
    assert parsed["task_count"] == 3
    # 버튼 · 스크립트 · 스타일은 할 일이 아니다. 위험한 링크는 버린다.
    assert all("초기화" not in i["text"] for s in parsed["sections"] for i in s["items"])
    assert parsed["links"] == [{"text": "📄 Notion — W01B 수업 자료", "url": "https://example.com/notion"}]


def test_markdown_keeps_written_checks_and_skips_tables():
    parsed = checklist_parser.parse_checklist(
        "# CLIP 주차\n"
        "## 정독\n"
        "- [x] Abstract · Figure 1 읽기\n"
        "- [ ] contrastive loss 수식 따라 적기\n"
        "> 구조 중심으로\n"
        "## 구현\n"
        "1. 미니 CLIP 학습 코드\n"
        "| 주차 | 논문 |\n|---|---|\n| 1주 | CLIP |\n"
        "[GitHub 저장소](https://github.com/example/tave)\n"
    )

    assert parsed["title"] == "CLIP 주차"
    first = parsed["sections"][0]
    assert first["title"] == "정독"
    assert [i["done"] for i in first["items"]] == [True, False]
    assert first["note"] == "구조 중심으로"
    assert parsed["sections"][1]["items"][0]["text"] == "미니 CLIP 학습 코드"
    assert parsed["links"][0]["url"] == "https://github.com/example/tave"
    assert any("표 3줄" in warning for warning in parsed["warnings"])


def test_plain_lines_are_items_so_old_goals_can_move_over():
    parsed = checklist_parser.parse_checklist("EC2 가 무엇인지 설명하기\n인스턴스 직접 실행하기\n")

    assert [i["text"] for i in parsed["sections"][0]["items"]] == [
        "EC2 가 무엇인지 설명하기",
        "인스턴스 직접 실행하기",
    ]


def test_empty_paste_is_rejected(client):
    assert client.post("/checklists/parse", json={"text": "  "}).status_code == 400


# --------------------------------
# 저장 · 체크
# --------------------------------

def _path_and_step(client):
    path = client.post("/learning-paths", json={"title": "추천시스템 Past vs Now"}).json()
    step = client.post(
        "/learning-steps",
        json={"learning_path_id": path["id"], "title": "1주차", "position": 0},
    ).json()
    return path, step


def _structure():
    parsed = checklist_parser.parse_checklist(ARTIFACT)
    return {"sections": parsed["sections"], "links": parsed["links"]}


def test_a_checklist_page_becomes_a_new_step(client):
    path, _ = _path_and_step(client)

    response = client.post(
        f"/learning-paths/{path['id']}/checklist-steps",
        json={"title": "2주차 — 인기 기반 & 내용 기반 추천", **_structure()},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["added"] == 3
    assert body["checklist"]["progress"] == {"done": 0, "total": 3}
    assert body["checklist"]["links"][0]["url"] == "https://example.com/notion"

    steps = client.get(f"/learning-steps?learning_path_id={path['id']}").json()
    assert [s["position"] for s in steps] == [0, 1]


def test_checking_starts_the_step_and_all_done_is_only_a_hint(client):
    _, step = _path_and_step(client)
    client.post(f"/learning-steps/{step['id']}/checklist/import", json=_structure())

    checklist = client.get(f"/learning-steps/{step['id']}/checklist").json()
    ids = [i["id"] for s in checklist["sections"] for i in s["items"]]

    first = client.patch(f"/checklist-items/{ids[0]}", json={"done": True}).json()
    assert first["started"] is True
    assert first["step_status"] == "in_progress"

    for item_id in ids[1:]:
        last = client.patch(f"/checklist-items/{item_id}", json={"done": True}).json()

    assert last["checklist"]["all_done"] is True
    # 모두 체크해도 단계를 저절로 끝내지 않는다.
    assert last["step_status"] == "in_progress"


def test_notes_and_links_are_not_checkable_or_counted(client):
    _, step = _path_and_step(client)
    body = client.post(f"/learning-steps/{step['id']}/checklist/import", json=_structure()).json()

    link_id = body["checklist"]["links"][0]["id"]
    assert client.patch(f"/checklist-items/{link_id}", json={"done": True}).status_code == 400
    assert body["checklist"]["progress"]["total"] == 3


def test_replace_swaps_the_list_and_an_empty_import_is_refused(client):
    _, step = _path_and_step(client)
    client.post(f"/learning-steps/{step['id']}/checklist/import", json=_structure())

    replaced = client.post(
        f"/learning-steps/{step['id']}/checklist/import",
        json={"sections": [{"title": "", "items": [{"text": "새 항목"}]}], "replace": True},
    ).json()
    assert replaced["checklist"]["progress"]["total"] == 1
    assert replaced["checklist"]["links"] == []

    empty = client.post(
        f"/learning-steps/{step['id']}/checklist/import",
        json={"sections": [{"title": "빈 묶음", "items": []}]},
    )
    assert empty.status_code == 400


def test_unsafe_links_cannot_be_saved(client):
    _, step = _path_and_step(client)

    response = client.post(
        f"/learning-steps/{step['id']}/checklist",
        json={"text": "나쁜 링크", "kind": "link", "url": "javascript:alert(1)"},
    )
    assert response.status_code == 422


def test_completing_a_step_mentions_unchecked_items(client):
    _, step = _path_and_step(client)
    client.post(f"/learning-steps/{step['id']}/checklist/import", json=_structure())

    body = client.post(f"/learning-steps/{step['id']}/complete").json()

    assert any("체크 안 한 항목 3개" in effect for effect in body["effects"])


def test_the_session_carries_the_checklist(client):
    _, step = _path_and_step(client)
    client.post(f"/learning-steps/{step['id']}/checklist/import", json=_structure())

    session = client.get(f"/learning-steps/{step['id']}/session").json()

    assert session["checklist"]["progress"]["total"] == 3
    assert session["checklist"]["next"][0]["text"] == "`u.user` / `u.item` 로드"


def test_today_shows_the_next_items_of_a_learning_task(client, db_session):
    _, step = _path_and_step(client)
    client.post(f"/learning-steps/{step['id']}/checklist/import", json=_structure())

    task = models.DailyPlanTask(
        plan_date=date(2026, 9, 16), position=0, task_type="learning_step",
        title="1주차", minutes=45, reason="테스트", status="planned",
        learning_step_id=step["id"],
    )
    db_session.add(task)
    db_session.commit()

    serialized = today_service.serialize_task(task)

    assert serialized["checklist"] == {
        "done": 0,
        "total": 3,
        "next": ["`u.user` / `u.item` 로드", "Gradio 앱 실행", "TF-IDF 벡터화"],
    }
