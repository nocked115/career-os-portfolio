"""Mission 023 - 기회 수집과 매칭."""

from datetime import datetime, timedelta

from app import models
from app.services import opportunity as opportunity_service


def _skills(client, spec):
    return {
        name: client.post(
            "/skills",
            json={"name": name, "category": "data", "level": level},
        ).json()
        for name, level in spec
    }


def _make_opportunity(client, **overrides):
    payload = {
        "opportunity_type": "job",
        "title": "Data Scientist Intern",
        "organization": "Test Co",
        "source": "manual",
        "description": "Python and SQL required.",
    }
    payload.update(overrides)

    return client.post("/opportunities", json=payload).json()


def _in_days(days):
    return (datetime.now() + timedelta(days=days)).isoformat()


# --------------------------------
# 수집
# --------------------------------

def test_collect_creates_opportunities(client):
    body = client.post("/opportunities/collect").json()

    assert body["created"] == 2
    assert [s["source"] for s in body["sources"]] == ["mock"]

    listed = client.get("/opportunities").json()
    assert len(listed) == 2


def test_collecting_twice_updates_instead_of_duplicating(client):
    client.post("/opportunities/collect")
    second = client.post("/opportunities/collect").json()

    assert second["created"] == 0
    assert second["updated"] == 2
    assert len(client.get("/opportunities").json()) == 2


def test_collection_links_skills_from_the_description(client):
    _skills(client, [("Python", 1), ("SQL", 0), ("Rust", 0)])

    client.post("/opportunities/collect")

    job = next(
        o
        for o in client.get("/opportunities").json()
        if o["opportunity_type"] == "job"
    )

    names = {
        s["name"]
        for s in client.get(f"/opportunities/{job['id']}/skills").json()
    }

    assert "Python" in names
    assert "SQL" in names
    assert "Rust" not in names


def test_job_opportunities_bridge_to_legacy_job(client):
    """레거시 대시보드가 계속 동작해야 한다."""
    client.post("/opportunities/collect")

    job_opportunity = next(
        o
        for o in client.get("/opportunities").json()
        if o["opportunity_type"] == "job"
    )

    assert job_opportunity["legacy_job_id"] is not None

    jobs = client.get("/jobs").json()
    assert [j["title"] for j in jobs] == ["Data Scientist Intern"]
    assert jobs[0]["id"] == job_opportunity["legacy_job_id"]


def test_competitions_do_not_create_legacy_jobs(client):
    client.post("/opportunities/collect")

    competition = next(
        o
        for o in client.get("/opportunities").json()
        if o["opportunity_type"] == "competition"
    )

    assert competition["legacy_job_id"] is None
    assert len(client.get("/jobs").json()) == 1


def test_recollecting_does_not_duplicate_legacy_jobs(client):
    client.post("/opportunities/collect")
    client.post("/opportunities/collect")

    assert len(client.get("/jobs").json()) == 1


def test_user_set_status_survives_recollection(client):
    client.post("/opportunities/collect")

    target = client.get("/opportunities").json()[0]
    client.patch(f"/opportunities/{target['id']}", json={"status": "interested"})

    client.post("/opportunities/collect")

    assert client.get(
        f"/opportunities/{target['id']}"
    ).json()["status"] == "interested"


# --------------------------------
# 매칭 점수
# --------------------------------

def test_passed_deadline_is_always_skipped(client):
    made = _skills(client, [("Python", 2)])

    opportunity = _make_opportunity(client, deadline=_in_days(-3))
    client.post(f"/opportunities/{opportunity['id']}/skills/{made['Python']['id']}")

    match = client.get(f"/opportunities/{opportunity['id']}/match").json()

    assert match["deadline_state"] == "passed"
    assert match["recommendation"] == "skip"
    assert "지났습니다" in " ".join(match["reasons"])


def test_match_without_skills_says_it_cannot_judge(client):
    opportunity = _make_opportunity(client, description="No known tech here.")

    match = client.get(f"/opportunities/{opportunity['id']}/match").json()

    assert match["skills_required"] == 0
    assert "찾지 못해" in " ".join(match["reasons"])
    # 모르는 것을 0 으로 치지 않는다 — 조선해양 데이터 사이언티스트가 10점으로 맨 아래 있었다.
    assert match["breakdown"]["relevance"] == 20
    assert match["breakdown"]["readiness"] == 15


def test_one_found_skill_is_not_full_readiness(client):
    # 공고에서 스킬 하나만 뽑혔다고 "다 갖췄다" 로 보지 않는다 (건강식품 영업 88점).
    made = _skills(client, [("Data Analysis", 2)])
    one = _make_opportunity(client, deadline=_in_days(40))
    client.post(f"/opportunities/{one['id']}/skills/{made['Data Analysis']['id']}")

    match = client.get(f"/opportunities/{one['id']}/match").json()

    assert (match["skills_i_have"], match["skills_required"]) == (1, 1)
    assert match["breakdown"]["readiness"] == 20  # 30 * 2/3


def test_breakdown_adds_up_to_the_score(client):
    made = _skills(client, [("Python", 1), ("SQL", 0)])

    opportunity = _make_opportunity(client, deadline=_in_days(40))
    for skill in made.values():
        client.post(f"/opportunities/{opportunity['id']}/skills/{skill['id']}")

    match = client.get(f"/opportunities/{opportunity['id']}/match").json()

    assert sum(match["breakdown"].values()) == match["match_score"]


def test_tight_deadline_lowers_the_score(client):
    made = _skills(client, [("Python", 2)])

    comfortable = _make_opportunity(client, deadline=_in_days(60))
    tight = _make_opportunity(
        client, title="Другой", deadline=_in_days(2)
    )

    for opportunity in (comfortable, tight):
        client.post(
            f"/opportunities/{opportunity['id']}"
            f"/skills/{made['Python']['id']}"
        )

    comfortable_match = client.get(
        f"/opportunities/{comfortable['id']}/match"
    ).json()
    tight_match = client.get(
        f"/opportunities/{tight['id']}/match"
    ).json()

    assert comfortable_match["match_score"] > tight_match["match_score"]
    assert tight_match["deadline_state"] == "tight"
    assert "촉박합니다" in " ".join(tight_match["reasons"])


def test_competition_carries_portfolio_value(client):
    made = _skills(client, [("Python", 2)])

    job = _make_opportunity(client, deadline=_in_days(40))
    competition = _make_opportunity(
        client,
        title="AI 공모전",
        opportunity_type="competition",
        deadline=_in_days(40),
    )

    for opportunity in (job, competition):
        client.post(
            f"/opportunities/{opportunity['id']}"
            f"/skills/{made['Python']['id']}"
        )

    job_match = client.get(f"/opportunities/{job['id']}/match").json()
    competition_match = client.get(
        f"/opportunities/{competition['id']}/match"
    ).json()

    assert (
        competition_match["breakdown"]["portfolio_value"]
        > job_match["breakdown"]["portfolio_value"]
    )
    assert "포트폴리오 증거로 남습니다" in " ".join(
        competition_match["reasons"]
    )


def test_score_is_persisted_on_the_opportunity(client):
    made = _skills(client, [("Python", 2)])
    opportunity = _make_opportunity(client, deadline=_in_days(40))
    client.post(
        f"/opportunities/{opportunity['id']}/skills/{made['Python']['id']}"
    )

    match = client.get(f"/opportunities/{opportunity['id']}/match").json()
    stored = client.get(f"/opportunities/{opportunity['id']}").json()

    assert stored["match_score"] == match["match_score"]
    assert stored["match_recommendation"] == match["recommendation"]
    assert stored["scored_at"] is not None


def test_matches_are_sorted_by_score(client):
    _skills(client, [("Python", 2), ("SQL", 1)])
    client.post("/opportunities/collect")

    scores = [
        m["match_score"]
        for m in client.get("/opportunities/matches").json()["matches"]
    ]

    assert scores == sorted(scores, reverse=True)


def test_recommended_excludes_skipped_and_respects_limit(client):
    made = _skills(client, [("Python", 2)])

    good = _make_opportunity(client, deadline=_in_days(60))
    client.post(f"/opportunities/{good['id']}/skills/{made['Python']['id']}")

    expired = _make_opportunity(
        client, title="지난 공고", deadline=_in_days(-1)
    )
    client.post(
        f"/opportunities/{expired['id']}/skills/{made['Python']['id']}"
    )

    body = client.get("/opportunities/recommended?limit=5").json()
    titles = [m["title"] for m in body["recommended"]]

    assert "지난 공고" not in titles
    assert body["count"] == len(body["recommended"])

    limited = client.get("/opportunities/recommended?limit=1").json()
    assert limited["count"] <= 1


def test_recommended_is_empty_when_nothing_is_worth_doing(client):
    """추천할 게 없으면 빈 목록이 정상이다. 억지로 채우지 않는다."""
    _make_opportunity(client, title="지난 공고", deadline=_in_days(-10))

    assert client.get("/opportunities/recommended").json()["count"] == 0


# --------------------------------
# 정적 경로 우선순위
# --------------------------------

def test_static_routes_are_not_swallowed_by_the_id_route(client):
    """/opportunities/collect 가 id 로 해석되면 안 된다."""
    assert client.post("/opportunities/collect").status_code == 200
    assert client.get("/opportunities/matches").status_code == 200
    assert client.get("/opportunities/recommended").status_code == 200


def test_unknown_opportunity_returns_404(client):
    assert client.get("/opportunities/9999/match").status_code == 404
    assert client.get("/opportunities/9999/skills").status_code == 404


# --------------------------------
# 서비스 단위
# --------------------------------

def test_days_until_handles_missing_deadline():
    assert opportunity_service.days_until(None) is None


def test_days_until_counts_forward_and_backward():
    assert opportunity_service.days_until(
        datetime.now() + timedelta(days=5)
    ) == 5
    assert opportunity_service.days_until(
        datetime.now() - timedelta(days=2)
    ) == -2


def test_skill_linking_is_case_insensitive(db_session):
    db_session.add(models.Skill(name="Python", category="lang", level=0))
    db_session.commit()

    opportunity = models.Opportunity(
        opportunity_type="job",
        title="Backend",
        source="manual",
        description="우리는 python 을 씁니다.",
    )
    db_session.add(opportunity)
    db_session.commit()

    linked = opportunity_service.link_skills(db_session, opportunity)

    assert [s.name for s in linked] == ["Python"]


def test_manual_opportunity_links_its_skills(client):
    """스킬이 연결되지 않은 기회는 분모만 늘린다.

    어느 스킬의 분자에도 안 들어가므로, 넣을수록 모든 스킬의
    비율이 내려간다. 그래서 연결은 선택이 아니라 필수다.
    """
    client.post("/skills", json={"name": "Python", "category": "lang"})
    client.post("/skills", json={"name": "SQL", "category": "data"})

    created = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "데이터 분석 인턴",
            "source": "manual",
            "description": "Python 과 SQL 을 사용합니다.",
        },
    ).json()

    assert sorted(s["name"] for s in created["skills"]) == ["Python", "SQL"]

    priority = client.get("/analytics/learning-priority").json()
    by_skill = {x["skill"]: x for x in priority["learning_priority"]}

    assert by_skill["Python"]["demand_count"] == 1
    assert by_skill["SQL"]["demand_count"] == 1


def test_skill_extraction_respects_word_boundaries(client):
    """전에는 부분 문자열 비교라 "Go" 가 "Google" 에 걸렸다."""
    client.post("/skills", json={"name": "Go", "category": "lang"})

    created = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "백엔드 인턴",
            "source": "manual",
            "description": "Google Cloud 를 씁니다.",
        },
    ).json()

    assert created["skills"] == []


def test_an_unregistered_skill_cannot_be_found(client):
    """등록되지 않은 스킬은 찾을 수 없다. 그게 이 방식의 한계다."""
    created = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "인턴",
            "source": "manual",
            "description": "Rust 경험자 우대.",
        },
    ).json()

    assert created["skills"] == []


def test_a_korean_posting_finds_a_skill_by_its_alias(client):
    """추출기는 이름을 글자 그대로 찾는다.

    한글 공고에 "Machine Learning" 은 안 걸린다. 별칭이 없으면
    한국 공고를 넣을 때마다 스킬 0개가 나오고, 그 기회는 분모만
    늘린다.
    """
    client.post(
        "/skills",
        json={
            "name": "Machine Learning",
            "category": "ai",
            "aliases": "머신러닝, ML",
        },
    )

    created = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "인공지능",
            "source": "manual",
            "description": "머신러닝 기반 추론 소프트웨어를 개발합니다.",
        },
    ).json()

    assert [s["name"] for s in created["skills"]] == ["Machine Learning"]


def test_aliases_also_respect_word_boundaries(client):
    """별칭이라고 규칙이 느슨해지면 안 된다."""
    client.post(
        "/skills",
        json={"name": "Machine Learning", "category": "ai", "aliases": "ML"},
    )

    created = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "인턴",
            "source": "manual",
            "description": "HTML 과 XML 을 다룹니다.",
        },
    ).json()

    assert created["skills"] == []


def test_a_korean_particle_does_not_hide_a_skill(client):
    """한국어는 조사가 명사에 붙는다.

    "딥러닝을" 처럼 조사가 붙으면 뒤에 한글이 온다. 뒤에 한글이
    오면 무조건 막는 규칙은 영문("Go" vs "Google")은 지키지만
    한국어를 통째로 놓친다. 실제 공고에서 이걸로 놓쳤다.
    """
    client.post(
        "/skills",
        json={"name": "Deep Learning", "category": "ai", "aliases": "딥러닝"},
    )

    created = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "데이터 분석",
            "source": "manual",
            "description": "머신러닝, 딥러닝을 비즈니스에 적용합니다.",
        },
    ).json()

    assert [s["name"] for s in created["skills"]] == ["Deep Learning"]


def test_a_compound_word_is_not_the_same_skill(client):
    """조사를 허용하되 합성어까지 같은 것으로 세지는 않는다."""
    client.post(
        "/skills",
        json={"name": "Deep Learning", "category": "ai", "aliases": "딥러닝"},
    )

    created = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "인턴",
            "source": "manual",
            "description": "딥러닝기술연구소에서 근무합니다.",
        },
    ).json()

    assert created["skills"] == []


def test_a_manually_added_opportunity_starts_as_interested(client):
    """직접 넣은 것은 이미 관심이 있다는 뜻이다.

    마감 추적은 interested 부터 시작한다. 수집기가 가져온
    discovered 와 구분하지 않으면, D-1 짜리를 직접 넣어도
    오늘 계획에 마감이 안 올라온다.
    """
    manual = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "내가 찾은 공고",
            "source": "manual",
        },
    ).json()

    assert manual["status"] == "interested"

    collected = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "수집된 공고",
            "source": "mock",
        },
    ).json()

    assert collected["status"] == "discovered"


def test_an_explicit_status_still_wins(client):
    body = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "이미 지원함",
            "source": "manual",
            "status": "applied",
        },
    ).json()

    assert body["status"] == "applied"


def test_an_opportunity_with_an_application_cannot_be_deleted(client):
    """지우면 지원서가 어느 기회에도 속하지 않게 된다.

    응답 검증이 그런 지원서를 거부해서 /applications 전체가 500 이
    난다. 화면 하나가 통째로 죽는다.
    """
    opportunity = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "지원한 공고",
            "source": "manual",
        },
    ).json()

    client.post(
        "/applications",
        json={"opportunity_id": opportunity["id"], "status": "interested"},
    )

    blocked = client.delete(f"/opportunities/{opportunity['id']}")

    assert blocked.status_code == 409
    assert "지원서" in blocked.json()["detail"]

    # 막았으니 목록은 계속 살아 있어야 한다.
    assert client.get("/applications").status_code == 200


def test_an_opportunity_without_applications_can_be_deleted(client):
    opportunity = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "그냥 저장만",
            "source": "manual",
        },
    ).json()

    assert client.delete(f"/opportunities/{opportunity['id']}").status_code == 200


def test_match_payload_carries_the_posting_url(client, db_session):
    """공고로 바로 갈 수 있어야 한다.

    이게 빠져 있어서 화면이 링크를 만들 재료가 없었다. 지원하러
    갈 때마다 주소를 다시 찾아야 했다.
    """
    from app import models

    db_session.add(
        models.Opportunity(
            title="어떤 공고",
            organization="어떤회사",
            opportunity_type="job",
            source="manual",
            source_url="https://example.com/jobs/1",
        )
    )
    db_session.commit()

    matches = client.get("/opportunities/matches").json()["matches"]

    assert matches
    assert matches[0]["source_url"] == "https://example.com/jobs/1"


def test_relink_picks_up_skills_added_after_the_posting(client, db_session):
    """스킬을 나중에 만들어도 이미 넣어둔 공고에 반영되어야 한다.

    link_skills 는 기회를 만들 때만 돈다. 그래서 본문에
    "강화학습" 이 있어도 그 스킬을 나중에 등록하면 영원히 안 걸리고,
    수요 계산이 옛 상태로 굳는다.
    """
    from app import models

    opportunity = models.Opportunity(
        title="연구원",
        organization="어떤회사",
        opportunity_type="job",
        source="manual",
        description="강화학습 기반 제어 연구를 합니다.",
    )
    db_session.add(opportunity)
    db_session.commit()

    # 이 시점엔 그런 스킬이 없다.
    assert opportunity.skills == []

    db_session.add(
        models.Skill(
            name="Reinforcement Learning",
            category="ai",
            aliases="강화학습",
        )
    )
    db_session.commit()

    result = client.post("/opportunities/relink-skills").json()

    assert result["count"] == 1
    assert "Reinforcement Learning" in result["changed"][0]["added"]

    db_session.refresh(opportunity)
    assert [s.name for s in opportunity.skills] == ["Reinforcement Learning"]


def test_relink_keeps_links_a_person_made_by_hand(client, db_session):
    """손으로 붙인 연결을 추출기가 못 찾는다고 지우면 안 된다."""
    from app import models

    skill = models.Skill(name="Kubernetes", category="infra")
    db_session.add(skill)

    opportunity = models.Opportunity(
        title="백엔드",
        organization="어떤회사",
        opportunity_type="job",
        source="manual",
        description="본문에는 그 단어가 없습니다.",
    )
    db_session.add(opportunity)
    db_session.flush()

    opportunity.skills.append(skill)
    db_session.commit()

    client.post("/opportunities/relink-skills")

    db_session.refresh(opportunity)
    assert [s.name for s in opportunity.skills] == ["Kubernetes"]
