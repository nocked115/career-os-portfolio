"""이월의 수명.

사흘 넘게 밀어둔 일은 사실 안 할 일일 가능성이 높다. 그런데 이월은
계획의 앞자리를 차지하므로, 그대로 두면 오늘 가장 중요한 일이 영영
계획에 못 들어간다.

실제로 그랬다 — 수요 0/3 인 스킬의 작업 셋이 사흘째 세 칸을 다
차지하는 동안 수요 3/3 인 1위 스킬은 한 번도 올라오지 못했다.
"""

from datetime import date, timedelta

from app import models
from app.services import today as today_service


def _leftover(db, *, days_ago, title, project_id=None):
    """days_ago 일 전에 처음 계획했고 아직 안 한 일."""
    origin = date.today() - timedelta(days=days_ago)

    task = models.DailyPlanTask(
        plan_date=date.today() - timedelta(days=1),
        position=0,
        task_type="project",
        title=title,
        minutes=45,
        reason="테스트",
        status="planned",
        carried_from=origin,
        project_id=project_id,
    )

    db.add(task)
    db.commit()

    return task


def test_a_fresh_leftover_still_comes_back(db_session):
    """어제 못 한 것은 그냥 버리지 않는다. 그게 이월의 목적이다."""
    _leftover(db_session, days_ago=1, title="어제 못 한 것")

    titles = [
        c["title"]
        for c in today_service.build_candidates(db_session, date.today())
    ]

    assert "어제 못 한 것" in titles


def test_a_leftover_past_its_lifetime_leaves_the_plan(db_session):
    limit = today_service.CARRY_OVER_LIMIT_DAYS

    _leftover(db_session, days_ago=limit + 1, title="사흘 넘게 미룬 것")

    titles = [
        c["title"]
        for c in today_service.build_candidates(db_session, date.today())
    ]

    assert "사흘 넘게 미룬 것" not in titles


def test_it_is_not_thrown_away_silently(db_session):
    """조용히 버리면 그것대로 나쁘다. 안 할 건지 물어봐야 한다."""
    limit = today_service.CARRY_OVER_LIMIT_DAYS

    _leftover(db_session, days_ago=limit + 2, title="사흘 넘게 미룬 것")

    stale = today_service.stale_carry_overs(db_session, date.today())

    assert len(stale) == 1
    assert stale[0]["title"] == "사흘 넘게 미룬 것"
    assert stale[0]["days_carried"] == limit + 2
    assert stale[0]["task_id"] is not None


def test_the_boundary_day_still_counts_as_fresh(db_session):
    """딱 한계일인 것은 아직 살아 있다. 넘어야 빠진다."""
    limit = today_service.CARRY_OVER_LIMIT_DAYS

    _leftover(db_session, days_ago=limit, title="딱 한계일")

    titles = [
        c["title"]
        for c in today_service.build_candidates(db_session, date.today())
    ]

    assert "딱 한계일" in titles
    assert today_service.stale_carry_overs(db_session, date.today()) == []


def test_the_top_skill_gets_into_the_plan_once_stale_work_steps_aside(
    client, db_session
):
    """이 기능을 만든 이유 그대로를 확인한다."""
    limit = today_service.CARRY_OVER_LIMIT_DAYS

    # 수요 없는 오래된 이월 셋이 자리를 다 차지하고 있었다
    for i in range(3):
        _leftover(
            db_session, days_ago=limit + 1, title=f"오래 미룬 일 {i}"
        )

    # 1위 스킬과 그 자료
    skill = models.Skill(name="Machine Learning", category="ai")
    db_session.add(skill)
    db_session.flush()

    opportunity = models.Opportunity(
        title="ML 공고",
        organization="어떤회사",
        opportunity_type="job",
        source="manual",
    )
    opportunity.skills.append(skill)
    db_session.add(opportunity)

    book = models.LearningResource(
        title="핸즈온 머신러닝",
        resource_type="book",
        duration_minutes=0,
        ownership="owned",
        skill_id=skill.id,
    )
    db_session.add(book)
    db_session.flush()

    db_session.add(
        models.LearningResourceSegment(
            learning_resource_id=book.id,
            position=0,
            label="1장 한눈에 보는 머신러닝",
            estimated_minutes=45,
        )
    )
    db_session.commit()

    plan = client.post("/today/plan?available_minutes=180").json()

    titles = " / ".join(t["title"] for t in plan["tasks"])

    assert "1장" in titles, f"1위 스킬이 계획에 없습니다: {titles}"
    assert "오래 미룬 일" not in titles

    # 그리고 물어본다
    assert len(client.get("/today/plan").json()["stale"]) == 3


def test_you_can_say_you_will_still_do_it(client, db_session):
    """치우는 길만 있으면 그건 묻는 게 아니라 버리는 것이다."""
    limit = today_service.CARRY_OVER_LIMIT_DAYS

    task = _leftover(db_session, days_ago=limit + 3, title="그래도 할 것")

    assert today_service.stale_carry_overs(db_session, date.today())

    response = client.post(f"/today/tasks/{task.id}/revive")
    assert response.status_code == 200

    # 더 이상 묻지 않고, 다시 계획 후보가 된다
    assert today_service.stale_carry_overs(db_session, date.today()) == []

    titles = [
        c["title"]
        for c in today_service.build_candidates(db_session, date.today())
    ]
    assert "그래도 할 것" in titles


def test_or_that_you_will_not(client, db_session):
    limit = today_service.CARRY_OVER_LIMIT_DAYS

    task = _leftover(db_session, days_ago=limit + 3, title="안 할 것")

    client.post(f"/today/tasks/{task.id}/skip")

    assert today_service.stale_carry_overs(db_session, date.today()) == []

    titles = [
        c["title"]
        for c in today_service.build_candidates(db_session, date.today())
    ]
    assert "안 할 것" not in titles
