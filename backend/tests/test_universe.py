"""Career Universe — 홈에 놓을 것.

여기서 새로 계산하는 것은 없다. 그래서 테스트는 "계산이 맞는가" 가
아니라 **"근거가 확인 가능한가"** 를 본다.
"""


def _planet(body, key):
    return next(p for p in body["planets"] if p["key"] == key)


def test_every_why_row_carries_a_number(client):
    """"HIGH" 만 있으면 확인할 방법이 없다.

    확인할 수 없는 것은 근거가 아니다 (DESIGN.md 원칙 1).
    """
    client.post("/skills", json={"name": "AWS", "category": "cloud"})

    body = client.get("/universe").json()

    for planet in body["planets"]:
        assert planet["why"], planet["key"]

        for row in planet["why"]:
            assert row["label"]
            assert row["level"] in ("high", "mid", "low")
            assert row["detail"], (planet["key"], row["label"])


def test_universe_has_all_six_planets(client):
    body = client.get("/universe").json()

    assert [p["key"] for p in body["planets"]] == [
        "learning",
        "projects",
        "opportunities",
        "experience",
        "applications",
        "library",
    ]


def test_universe_works_on_an_empty_install(client):
    """아무것도 없어도 홈은 떠야 한다. 빈 화면이 아니라 빈 상태다."""
    body = client.get("/universe").json()

    assert body["me"]["name"] == ""
    assert body["evidence"]["total"] == 0
    assert len(body["planets"]) == 6


def test_reading_the_universe_does_not_rescore_opportunities(client):
    """조회가 조용히 쓰기가 되면 안 된다.

    홈을 열 때마다 채점하면 데이터가 계속 바뀌고,
    같은 화면을 두 번 봐도 값이 달라진다.
    """
    client.post(
        "/opportunities",
        json={
            "title": "데이터 공모전",
            "opportunity_type": "competition",
            "source": "manual",
        },
    )

    client.get("/universe")

    stored = client.get("/opportunities").json()[0]
    assert stored["match_score"] is None

    planet = _planet(client.get("/universe").json(), "opportunities")
    unscored = next(
        row for row in planet["why"] if row["label"] == "채점 안 됨"
    )
    assert "1건" in unscored["detail"]


def test_evidence_stars_come_from_the_evidence_service(client):
    """배경의 별은 장식이 아니라 쌓인 증거의 실제 개수다."""
    body = client.get("/universe").json()
    direct = client.get("/analytics/evidence").json()

    assert body["evidence"]["total"] == direct["total"]
    assert body["evidence"]["breakdown"] == direct["breakdown"]


def test_library_planet_reports_what_it_set_aside(client):
    """원칙 2 는 궤도에서도 지켜진다."""
    aws = client.post(
        "/skills", json={"name": "AWS", "category": "cloud"}
    ).json()
    other = client.post(
        "/skills", json={"name": "Cooking", "category": "x"}
    ).json()

    job = client.post(
        "/jobs", json={"company": "A", "title": "T", "role": "r"}
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{aws['id']}")

    client.post(
        "/resources",
        json={
            "title": "EC2 기초",
            "duration_minutes": 20,
            "skill_id": aws["id"],
        },
    )
    client.post(
        "/resources",
        json={
            "title": "파스타",
            "duration_minutes": 10,
            "skill_id": other["id"],
        },
    )

    planet = _planet(client.get("/universe").json(), "library")

    aside = next(
        row for row in planet["why"] if row["label"] == "안 봐도 되는 것"
    )
    assert "1개는 지금 아님" in aside["detail"]


def test_every_planet_lands_where_its_name_promises(client):
    """MY LIBRARY 를 눌렀는데 학습 경로가 열리면 고른 것과 다른 데 온 것이다.

    화면(route)만으로는 부족하다. 같은 화면 안에서도
    어디로 갈지(section)까지 정해야 한다.
    """
    planets = {p["key"]: p for p in client.get("/universe").json()["planets"]}

    assert planets["library"]["route"] == "library"
    assert planets["learning"]["route"] == "learning"
    assert planets["learning"]["section"] == "paths"

    # Projects 와 Experience 는 이제 각자의 화면을 갖는다.
    assert planets["projects"]["route"] == "projects"
    assert planets["experience"]["route"] == "proof"


def test_no_two_planets_share_the_same_destination(client):
    """두 천체가 완전히 같은 곳으로 가면 하나는 거짓말이다."""
    planets = client.get("/universe").json()["planets"]

    destinations = [(p["route"], p["section"]) for p in planets]

    assert len(destinations) == len(set(destinations))


def test_readiness_never_claims_a_career_is_a_percent_done(client):
    """"커리어 68% 완료" 같은 숫자는 만들지 않는다.

    커리어에 완료율은 없고, 그런 숫자는 근거를 댈 수 없다.
    중앙의 퍼센트는 목표 직무 스킬의 평균 숙련도이고,
    무엇의 퍼센트인지가 항상 같이 온다.
    """
    empty = client.get("/universe").json()["readiness"]
    assert empty["percent"] == 0
    assert empty["skill_count"] == 0

    for level in (0, 2, 4):
        client.post(
            "/skills",
            json={"name": f"S{level}", "category": "x", "level": level},
        )

    readiness = client.get("/universe").json()["readiness"]

    # (0 + 2 + 4) / (3 * 4) = 50%
    assert readiness["percent"] == 50
    assert readiness["skill_count"] == 3
    assert readiness["basis"] == "등록된 스킬"
    assert "평균 숙련도" in readiness["detail"]


def test_readiness_follows_the_target_career_when_there_is_one(client):
    """목표가 있으면 그 목표의 스킬만 센다.

    목표와 무관한 스킬까지 넣으면 준비도가 실제보다 좋아 보인다.
    """
    on_target = client.post(
        "/skills", json={"name": "AWS", "category": "x", "level": 4}
    ).json()
    client.post(
        "/skills", json={"name": "Cooking", "category": "x", "level": 0}
    )

    target = client.post(
        "/target-careers",
        json={"title": "Data / AI", "is_active": True},
    ).json()
    client.post(f"/target-careers/{target['id']}/skills/{on_target['id']}")

    readiness = client.get("/universe").json()["readiness"]

    assert readiness["basis"] == "Data / AI 스킬"
    assert readiness["skill_count"] == 1
    assert readiness["percent"] == 100


def test_every_planet_carries_a_badge_with_a_real_count(client):
    """배지에는 실제 개수만 쓴다. "New!" 같은 말은 개수를 감춘다."""
    body = client.get("/universe").json()

    for planet in body["planets"]:
        assert planet["badge"], planet["key"]
