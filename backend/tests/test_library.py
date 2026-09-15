"""My Learning Library — 내가 가진 것 중에서 고른다 (Phase 2).

Career OS 는 새 자료를 추천하지 않는다.
쌓아둔 것 중에서 지금 필요한 것만 꺼내고 나머지는 치운다.
"""

from app.services import library as library_service


def _skill(client, name="AWS"):
    return client.post(
        "/skills", json={"name": name, "category": "cloud"}
    ).json()


def _resource(client, skill, **kw):
    payload = {
        "title": "자료",
        "skill_id": skill["id"],
        "duration_minutes": 30,
    }
    payload.update(kw)
    return client.post("/resources", json=payload).json()


def _step(client, skill):
    path = client.post(
        "/learning-paths", json={"title": "AWS", "skill_id": skill["id"]}
    ).json()
    return client.post(
        "/learning-steps",
        json={"learning_path_id": path["id"], "title": "EC2", "position": 0},
    ).json()


def _segment(client, resource, label, minutes, position=0):
    return client.post(
        f"/resources/{resource['id']}/segments",
        json={"label": label, "position": position, "estimated_minutes": minutes},
    ).json()


# --------------------------------
# 종이책 — URL 없는 자료
# --------------------------------

def test_a_paper_book_needs_no_url(client):
    """내가 가진 종이책에는 URL 이 없다.

    Phase 2 이전에는 url 이 NOT NULL 이라 아예 넣을 수 없었다.
    """
    skill = _skill(client)

    book = client.post(
        "/resources",
        json={
            "title": "AWS 완벽 가이드",
            "resource_type": "book",
            "ownership": "owned",
            "total_units": 420,
            "unit_label": "쪽",
            "skill_id": skill["id"],
        },
    )

    assert book.status_code == 200
    assert book.json()["url"] is None
    assert book.json()["ownership"] == "owned"


def test_ownership_is_validated(client):
    skill = _skill(client)

    bad = client.post(
        "/resources",
        json={"title": "X", "ownership": "borrowed", "skill_id": skill["id"]},
    )

    assert bad.status_code == 422


def test_ownership_defaults_to_saved(client):
    skill = _skill(client)

    assert _resource(client, skill)["ownership"] == "saved"


# --------------------------------
# 라이브러리 조회
# --------------------------------

def test_library_summarizes_what_i_have(client):
    skill = _skill(client)

    _resource(client, skill, title="책", resource_type="book", ownership="owned")
    _resource(client, skill, title="영상", resource_type="video")
    _resource(client, skill, title="사고 싶은 책", resource_type="book",
              ownership="wishlist")

    body = client.get("/library").json()

    assert body["summary"]["total"] == 3
    assert body["summary"]["by_type"]["book"] == 2
    assert body["summary"]["by_ownership"]["owned"] == 1
    assert body["summary"]["by_ownership"]["wishlist"] == 1


def test_library_filters(client):
    skill = _skill(client)

    _resource(client, skill, title="책", resource_type="book", ownership="owned")
    _resource(client, skill, title="영상", resource_type="video")

    owned = client.get("/library?ownership=owned").json()
    assert [i["title"] for i in owned["items"]] == ["책"]

    videos = client.get("/library?resource_type=video").json()
    assert [i["title"] for i in videos["items"]] == ["영상"]


# --------------------------------
# 조각
# --------------------------------

def test_a_book_can_be_split_into_chapters(client):
    """"책 한 권을 읽으세요" 가 아니라 "3장을 15분 읽으세요" 여야 한다."""
    skill = _skill(client)
    book = _resource(client, skill, title="AWS 완벽 가이드", resource_type="book")

    _segment(client, book, "1장 — 클라우드 기초", 20, position=0)
    _segment(client, book, "3장 — EC2 기초", 15, position=1)

    segments = client.get(f"/resources/{book['id']}/segments").json()

    assert [s["label"] for s in segments] == [
        "1장 — 클라우드 기초",
        "3장 — EC2 기초",
    ]


def test_duplicate_segment_position_is_rejected(client):
    skill = _skill(client)
    book = _resource(client, skill)

    _segment(client, book, "1장", 10, position=0)

    duplicate = client.post(
        f"/resources/{book['id']}/segments",
        json={"label": "다른 1장", "position": 0, "estimated_minutes": 10},
    )

    assert duplicate.status_code == 409


def test_completing_every_segment_completes_the_resource(client):
    skill = _skill(client)
    book = _resource(client, skill)

    first = _segment(client, book, "1장", 10, position=0)
    second = _segment(client, book, "2장", 10, position=1)

    client.post(f"/segments/{first['id']}/complete")

    body = client.post(f"/segments/{second['id']}/complete").json()

    assert body["segment"]["status"] == "completed"
    assert body["segment"]["completed_at"] is not None
    assert body["resource_status"] == "completed"


def test_partial_progress_does_not_complete_the_resource(client):
    skill = _skill(client)
    book = _resource(client, skill)

    first = _segment(client, book, "1장", 10, position=0)
    _segment(client, book, "2장", 10, position=1)

    body = client.post(f"/segments/{first['id']}/complete").json()

    assert body["resource_status"] != "completed"


def test_library_reports_segment_progress(client):
    skill = _skill(client)
    book = _resource(client, skill)

    first = _segment(client, book, "1장", 10, position=0)
    _segment(client, book, "2장", 10, position=1)

    client.post(f"/segments/{first['id']}/complete")

    item = client.get("/library").json()["items"][0]

    assert item["segments_total"] == 2
    assert item["segments_done"] == 1


# --------------------------------
# 선별 — 이 제품의 핵심
# --------------------------------

def _step_with_resources(client):
    skill = _skill(client)
    step = _step(client, skill)

    book = _resource(client, skill, title="보유 책", resource_type="book",
                     ownership="owned", importance="primary", duration_minutes=0)
    _segment(client, book, "3장", 15, position=0)

    practice = _resource(client, skill, title="EC2 실습",
                         resource_type="practice", importance="primary",
                         duration_minutes=20)
    video = _resource(client, skill, title="저장한 영상",
                      resource_type="video", importance="supplementary",
                      duration_minutes=10)
    paper = _resource(client, skill, title="백서", resource_type="paper",
                      importance="deep_dive", duration_minutes=60)

    for resource in (book, practice, video, paper):
        client.post(f"/learning-steps/{step['id']}/resources/{resource['id']}")

    return step, book


def test_selection_fits_the_available_time(client):
    step, _ = _step_with_resources(client)

    body = client.get(
        f"/learning-steps/{step['id']}/selection?available_minutes=45"
    ).json()

    assert body["selected_minutes"] <= 45


def test_selection_puts_the_rest_away_explicitly(client):
    """치운 것을 보여주는 것까지가 선별이다.

    "나머지 N개 → 지금은 볼 필요 없음" 을 빼면 그냥 목록이 된다.
    """
    step, _ = _step_with_resources(client)

    body = client.get(
        f"/learning-steps/{step['id']}/selection?available_minutes=45"
    ).json()

    assert body["skipped_count"] > 0
    assert "지금은 볼 필요 없음" in body["skipped_message"]

    for item in body["skipped"]:
        assert item["skip_reason"]


def test_primary_comes_before_supplementary(client):
    step, _ = _step_with_resources(client)

    body = client.get(
        f"/learning-steps/{step['id']}/selection?available_minutes=45"
    ).json()

    titles = [i["title"] for i in body["selected"]]

    assert titles[0].startswith("보유 책")


def test_owned_beats_saved_at_the_same_importance(client):
    """이미 가진 것을 두고 저장만 해둔 것을 먼저 보라고 하면 안 된다."""
    skill = _skill(client)
    step = _step(client, skill)

    saved = _resource(client, skill, title="저장한 것", ownership="saved",
                      importance="primary", duration_minutes=20)
    owned = _resource(client, skill, title="가진 것", ownership="owned",
                      importance="primary", duration_minutes=20)

    for resource in (saved, owned):
        client.post(f"/learning-steps/{step['id']}/resources/{resource['id']}")

    body = client.get(
        f"/learning-steps/{step['id']}/selection?available_minutes=20"
    ).json()

    assert body["selected"][0]["title"] == "가진 것"


def test_completed_segments_are_not_offered_again(client):
    skill = _skill(client)
    step = _step(client, skill)

    book = _resource(client, skill, title="책", duration_minutes=0)
    first = _segment(client, book, "1장", 15, position=0)
    _segment(client, book, "2장", 15, position=1)

    client.post(f"/learning-steps/{step['id']}/resources/{book['id']}")
    client.post(f"/segments/{first['id']}/complete")

    body = client.get(
        f"/learning-steps/{step['id']}/selection?available_minutes=60"
    ).json()

    labels = [i["title"] for i in body["selected"]]
    assert not any("1장" in t for t in labels)
    assert any("2장" in t for t in labels)


def test_resource_without_an_estimate_is_not_planned(client):
    """얼마나 걸릴지 모르는 걸 넣으면 계획이 거짓이 된다."""
    skill = _skill(client)
    step = _step(client, skill)

    unknown = _resource(client, skill, title="시간 모르는 자료",
                        duration_minutes=0)
    client.post(f"/learning-steps/{step['id']}/resources/{unknown['id']}")

    body = client.get(
        f"/learning-steps/{step['id']}/selection?available_minutes=60"
    ).json()

    assert body["selected"] == []
    assert body["skipped"][0]["skip_reason"] == "예상 시간이 없습니다"


def test_nothing_selected_when_there_is_no_time(client):
    step, _ = _step_with_resources(client)

    body = client.get(
        f"/learning-steps/{step['id']}/selection?available_minutes=0"
    ).json()

    assert body["selected"] == []
    assert body["skipped_count"] > 0


def test_selection_on_a_step_with_no_resources(client):
    skill = _skill(client)
    step = _step(client, skill)

    body = client.get(f"/learning-steps/{step['id']}/selection").json()

    assert body["selected"] == []
    assert body["skipped_message"] is None


# --------------------------------
# 서비스 단위
# --------------------------------

def test_sort_prefers_importance_then_ownership():
    items = [
        {"importance": "supplementary", "ownership": "owned", "minutes": 10},
        {"importance": "primary", "ownership": "saved", "minutes": 10},
        {"importance": "primary", "ownership": "owned", "minutes": 10},
    ]

    ordered = sorted(items, key=library_service._sort_key)

    assert ordered[0]["importance"] == "primary"
    assert ordered[0]["ownership"] == "owned"
    assert ordered[-1]["importance"] == "supplementary"


# --------------------------------
# 라이브러리 전체 선별
#
# "영상 43개 · 책 11권 — 지금은 볼 필요 없습니다"
# 이 문장이 성립하는지 확인한다.
# --------------------------------

def _lib_skill(client, name, level=0):
    return client.post(
        "/skills",
        json={"name": name, "category": "x", "level": level},
    ).json()


def _lib_resource(client, skill_id, title, minutes, **extra):
    return client.post(
        "/resources",
        json={
            "title": title,
            "url": "https://example.com",
            "duration_minutes": minutes,
            "skill_id": skill_id,
            **extra,
        },
    ).json()


def _lib_focus(client, name="AWS"):
    """공고에 연결해서 이 스킬을 우선순위 1위로 만든다."""
    skill = _lib_skill(client, name)

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    return skill


def test_selection_sets_aside_what_is_not_the_focus(client):
    """관련 없는 자료는 시간이 남아도 치운다.

    시간으로만 자르면 "오늘은 시간이 없어서" 가 되고,
    내일은 보라는 뜻이 된다. 그건 선별이 아니다.
    """
    aws = _lib_focus(client)
    other = _lib_skill(client, "Cooking")

    _lib_resource(client, aws["id"], "EC2 기초", 20)
    _lib_resource(client, other["id"], "파스타 만들기", 10)

    body = client.get("/library/selection?available_minutes=600").json()

    assert body["focus_skill"] == "AWS"
    assert [item["title"] for item in body["selected"]] == ["EC2 기초"]

    aside = body["set_aside"]
    assert len(aside) == 1
    assert aside[0]["title"] == "파스타 만들기"
    assert "관련이 없습니다" in aside[0]["skip_reason"]


def test_selection_counts_what_it_set_aside_by_type(client):
    """개수만으로는 부담이 안 덜린다. 무엇을 안 봐도 되는지 밝힌다."""
    aws = _lib_focus(client)
    other = _lib_skill(client, "Cooking")

    _lib_resource(client, aws["id"], "EC2 기초", 20)

    for index in range(3):
        _lib_resource(
            client, other["id"], f"영상 {index}", 10,
            resource_type="video",
        )
    _lib_resource(
        client, other["id"], "요리책", 30, resource_type="book"
    )

    body = client.get("/library/selection?available_minutes=600").json()

    assert body["set_aside_count"] == 4
    assert body["set_aside_by_type"] == [
        {"resource_type": "video", "count": 3},
        {"resource_type": "book", "count": 1},
    ]
    assert body["message"] is not None


def test_selection_does_not_bury_finished_work_in_the_set_aside(client):
    """끝낸 자료를 "안 봐도 됨" 으로 묶으면 성과가 지워진다.

    치운 것이 아니라 완료로 따로 센다.
    """
    aws = _lib_focus(client)

    _lib_resource(client, aws["id"], "EC2 기초", 20)
    done = _lib_resource(client, aws["id"], "끝낸 강의", 30)
    client.patch(f"/resources/{done['id']}", json={"status": "completed"})

    body = client.get("/library/selection?available_minutes=600").json()

    titles = [item["title"] for item in body["set_aside"]]
    assert "끝낸 강의" not in titles
    assert body["completed_count"] == 1


def test_selection_says_nothing_is_set_aside_when_nothing_is(client):
    """치운 게 없으면 그 문장을 띄우지 않는다.

    빈 상태에 "지금은 볼 필요 없습니다" 를 띄우면 거짓말이다.
    """
    aws = _lib_focus(client)
    _lib_resource(client, aws["id"], "EC2 기초", 20)

    body = client.get("/library/selection?available_minutes=600").json()

    assert body["set_aside_count"] == 0
    assert body["set_aside_by_type"] == []
    assert body["message"] is None


def test_selection_without_a_focus_skill_sets_everything_aside(client):
    """집중할 스킬이 없으면 무엇을 고를 근거가 없다.

    아무거나 고르지 않는다. 왜 못 고르는지 말한다.
    """
    skill = _lib_skill(client, "AWS")
    _lib_resource(client, skill["id"], "EC2 기초", 20)

    body = client.get("/library/selection?available_minutes=600").json()

    # 공고가 없어 우선순위 점수가 0 이라도 스킬 자체는 집중 대상이 된다.
    # 스킬이 하나도 없을 때만 집중 스킬이 사라진다.
    assert body["focus_skill"] == "AWS"

    empty = client.get("/library/selection?available_minutes=600")
    assert empty.status_code == 200
