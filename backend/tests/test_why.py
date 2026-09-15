"""Why this plan? — 판단의 근거.

이 화면의 값은 새로 계산하지 않는다. 그래서 테스트가 확인할 것은
"계산이 맞는가" 가 아니라 **"근거가 빠지지 않았는가"** 다.
"""


def _keys(body):
    return [cell["key"] for cell in body["inputs"]]


def _cell(body, key):
    return next(cell for cell in body["inputs"] if cell["key"] == key)


def test_why_lists_every_input_even_when_empty(client):
    """데이터가 없어도 칸은 사라지지 않는다.

    칸이 사라지면 무엇을 못 봤는지 알 수 없다.
    available=false 로 남겨서 빠진 것을 보여준다.
    """
    client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    )

    body = client.get("/today/why").json()

    assert _keys(body) == [
        "target",
        "market",
        "gap",
        "project",
        "learning",
        "library",
        "deadline",
        "time",
    ]

    assert _cell(body, "market")["available"] is False
    assert _cell(body, "project")["available"] is False
    assert _cell(body, "learning")["available"] is False


def test_why_reports_what_it_could_not_use(client):
    client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    )

    body = client.get("/today/why").json()
    joined = " ".join(body["limits"])

    # 계산 용어(MARKET)가 아니라 화면에 보이는 이름으로 말한다.
    assert "시장 수요" in joined
    assert "프로젝트" in joined
    assert "MARKET" not in joined


def test_market_counts_every_kind_of_opportunity(client):
    """전에는 공고(Job)와 기회(Opportunity)가 다른 모수를 썼다.

    브리지가 job 타입만 넘겨서 공모전·대외활동이 빠졌고, 같은 "수요" 를
    두 칸이 다르게 셌다. 이제 Job 으로 들어온 것도 Opportunity 에
    남으므로 칸도 하나면 된다.
    """
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    client.post(
        "/opportunities",
        json={
            "title": "데이터 공모전",
            "opportunity_type": "competition",
            "source": "manual",
        },
    )

    body = client.get("/today/why").json()

    # 공고 1건 + 공모전 1건 = 기회 2건. 공모전도 수요로 센다.
    assert _cell(body, "market")["value"] == "AWS · 1 / 2"

    # 같은 말을 하는 칸이 둘 있으면 하나는 잡음이다.
    assert "signal" not in _keys(body)


def test_why_carries_the_decision_with_reasons(client):
    """근거만 있고 결론이 없으면 화면이 반쪽이다."""
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    path = client.post(
        "/learning-paths",
        json={"title": "AWS 배포 익히기", "skill_id": skill["id"]},
    ).json()
    client.post(
        "/learning-steps",
        json={
            "learning_path_id": path["id"],
            "title": "EC2 기초",
            "estimated_minutes": 30,
            "position": 0,
        },
    )

    client.post("/today/plan?available_minutes=60&intensity=normal")

    decision = client.get("/today/why").json()["decision"]

    assert decision["total_tasks"] > 0
    assert all(task["reason"] for task in decision["tasks"])


def test_why_without_skills_says_so(client):
    body = client.get("/today/why").json()

    assert body["focus_skill"] is None
    assert body["inputs"] == []
    assert body["decision"] is None
    assert body["limits"] == ["등록된 스킬이 없어 계획을 세울 수 없습니다."]


def test_every_input_can_be_unfolded(client):
    """펼쳐서 보여줄 게 없으면 화살표는 장식이다.

    각 문장이 어디서 나왔는지 — 계산에 들어간 실제 숫자를 갖고 있어야
    한다. 데이터가 없어 못 쓴 입력은 예외다.
    """
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    body = client.get("/today/why").json()

    for cell in body["inputs"]:
        assert cell["glyph"]

        if cell["available"]:
            assert cell["evidence"], cell["key"]


def test_market_evidence_names_the_numbers_behind_the_percentage(client):
    """"시장 수요 100%" 가 어디서 나왔는지 펼쳐 볼 수 있어야 한다."""
    skill = client.post(
        "/skills",
        json={"name": "AWS", "category": "cloud", "level": 0},
    ).json()

    job = client.post(
        "/jobs",
        json={"company": "A", "title": "T", "role": "r"},
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    client.post(
        "/jobs",
        json={"company": "B", "title": "T2", "role": "r"},
    )

    market = _cell(client.get("/today/why").json(), "market")

    joined = " ".join(market["evidence"])

    assert "모아둔 기회 2건" in joined
    assert "AWS · 1 / 2건" in joined
    assert "50%" in joined
