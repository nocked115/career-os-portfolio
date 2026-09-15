"""Today Plan — 시스템이 오늘 할 일을 결정한다 (Phase 1).

Todo 앱과의 차이: 사용자가 할 일을 넣는 게 아니라
우선순위·진행도·마감·가용 시간을 보고 시스템이 정한다.
"""

from datetime import date, datetime, timedelta

from app import models
from app.services import today as today_service


def _skill(client, name, level=0):
    return client.post(
        "/skills", json={"name": name, "category": "x", "level": level}
    ).json()


def _demand(client, skills):
    job = client.post(
        "/jobs", json={"company": "A", "title": "T", "role": "r"}
    ).json()
    for s in skills:
        client.post(f"/jobs/{job['id']}/skills/{s['id']}")
    return job


def _path_with_step(client, skill, minutes=30, title="EC2 Fundamentals"):
    path = client.post(
        "/learning-paths", json={"title": "AWS", "skill_id": skill["id"]}
    ).json()
    step = client.post(
        "/learning-steps",
        json={
            "learning_path_id": path["id"],
            "title": title,
            "position": 0,
            "estimated_minutes": minutes,
        },
    ).json()
    return path, step


# --------------------------------
# 빈 상태
# --------------------------------

def test_plan_is_empty_before_it_is_made(client):
    body = client.get("/today/plan").json()

    assert body["tasks"] == []
    assert body["total_tasks"] == 0
    assert body["done_tasks"] == 0


def test_intensities_are_listed(client):
    keys = [i["key"] for i in client.get("/today/intensities").json()["intensities"]]

    assert keys == ["light", "normal", "deep_focus"]


def test_unknown_intensity_is_rejected(client):
    assert client.post("/today/plan?intensity=hardcore").status_code == 422


# --------------------------------
# 계획 생성
# --------------------------------

def test_plan_uses_the_top_priority_skill(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws)

    body = client.post("/today/plan?available_minutes=120").json()

    assert body["total_tasks"] >= 1

    first = body["tasks"][0]
    assert first["title"] == "EC2 Fundamentals"
    assert first["task_type"] == "learning_step"
    assert "우선순위 1위" in first["reason"]


def test_every_task_explains_itself(client):
    """설명할 수 없으면 계획에 넣지 않는다."""
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws)

    body = client.post("/today/plan").json()

    for task in body["tasks"]:
        assert task["reason"]


def test_plan_respects_available_minutes(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws, minutes=60)

    project = client.post(
        "/projects", json={"name": "AWS Deploy", "daily_minutes": 60}
    ).json()
    client.post(f"/projects/{project['id']}/skills/{aws['id']}")

    body = client.post("/today/plan?available_minutes=45").json()

    assert body["planned_minutes"] <= 45


def test_empty_time_produces_no_tasks(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws)

    body = client.post("/today/plan?available_minutes=0").json()

    assert body["tasks"] == []


# --------------------------------
# 강도
# --------------------------------

def test_deep_focus_gives_fewer_longer_blocks(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws, minutes=60)

    project = client.post(
        "/projects", json={"name": "AWS Deploy", "daily_minutes": 60}
    ).json()
    client.post(f"/projects/{project['id']}/skills/{aws['id']}")

    light = client.post(
        "/today/plan?available_minutes=120&intensity=light"
    ).json()
    deep = client.post(
        "/today/plan?available_minutes=120&intensity=deep_focus"
    ).json()

    # 가볍게: 한 덩어리를 짧게 자른다
    assert max(t["minutes"] for t in light["tasks"]) <= 30

    # 몰입: 덩어리를 자르지 않고 원래 길이대로 둔다
    assert max(t["minutes"] for t in deep["tasks"]) >= 60


def test_short_work_is_not_dropped_in_deep_focus(client):
    """일이 짧다고 버리지 않는다.

    min_block 은 남은 자투리 시간을 쓰지 않는다는 뜻이지,
    40분짜리 최우선 학습을 빼라는 뜻이 아니다.
    """
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws, minutes=40, title="짧은 단계")

    body = client.post(
        "/today/plan?available_minutes=120&intensity=deep_focus"
    ).json()

    assert "짧은 단계" in [t["title"] for t in body["tasks"]]


def test_intensity_label_is_returned(client):
    body = client.post("/today/plan?intensity=deep_focus").json()

    assert body["intensity"] == "deep_focus"
    assert body["intensity_label"] == "몰입"


# --------------------------------
# 마감
# --------------------------------

def _application_due_in(client, days, title="Data Scientist Intern"):
    opportunity = client.post(
        "/opportunities",
        json={"opportunity_type": "job", "title": title, "source": "manual"},
    ).json()

    deadline = (datetime.now() + timedelta(days=days)).isoformat()

    return client.post(
        "/applications",
        json={
            "opportunity_id": opportunity["id"],
            "status": "preparing",
            "deadline": deadline,
        },
    ).json()


def test_urgent_deadline_comes_first(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws)

    _application_due_in(client, 2)

    body = client.post("/today/plan?available_minutes=120").json()

    first = body["tasks"][0]
    assert first["task_type"] == "application"
    assert "마감까지 2일" in first["reason"]


def test_far_deadline_does_not_take_over_today(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws)

    _application_due_in(client, 20)

    body = client.post("/today/plan?available_minutes=120").json()

    assert body["tasks"][0]["task_type"] != "application"


def test_deadlines_endpoint_excludes_past_and_finished(client):
    _application_due_in(client, 5, "곧 마감")

    past = _application_due_in(client, 5, "지난 것")
    client.patch(
        f"/applications/{past['id']}",
        json={"deadline": (datetime.now() - timedelta(days=3)).isoformat()},
    )

    applied = _application_due_in(client, 5, "이미 지원함")
    client.patch(f"/applications/{applied['id']}", json={"status": "applied"})

    titles = [d["title"] for d in client.get("/today/deadlines").json()["deadlines"]]

    assert titles == ["곧 마감"]


def test_deadlines_are_sorted_by_urgency(client):
    _application_due_in(client, 9, "나중")
    _application_due_in(client, 2, "급함")

    titles = [d["title"] for d in client.get("/today/deadlines").json()["deadlines"]]

    assert titles == ["급함", "나중"]


# --------------------------------
# 완료 / 건너뛰기
# --------------------------------

def test_completing_a_learning_task_updates_the_real_step(client):
    """체크만 하고 원래 데이터가 그대로면 진행도가 거짓이 된다."""
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    path, step = _path_with_step(client, aws)

    plan = client.post("/today/plan").json()
    task = plan["tasks"][0]

    body = client.post(f"/today/tasks/{task['id']}/complete").json()

    assert body["task"]["status"] == "done"
    assert body["task"]["completed_at"] is not None
    assert any("학습 단계 완료" in e for e in body["effects"])

    assert client.get(
        f"/learning-steps/{step['id']}"
    ).json()["status"] == "completed"
    assert client.get(
        f"/learning-paths/{path['id']}"
    ).json()["progress_percent"] == 100


def test_completion_flows_through_to_priority(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws)

    before = client.get(
        "/analytics/learning-priority"
    ).json()["learning_priority"][0]["priority_score"]

    plan = client.post("/today/plan").json()
    client.post(f"/today/tasks/{plan['tasks'][0]['id']}/complete")

    after = client.get(
        "/analytics/learning-priority"
    ).json()["learning_priority"][0]["priority_score"]

    assert after < before


def test_done_count_is_reported(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws)

    plan = client.post("/today/plan").json()
    client.post(f"/today/tasks/{plan['tasks'][0]['id']}/complete")

    body = client.get("/today/plan").json()

    assert body["done_tasks"] == 1
    assert body["done_minutes"] > 0


def test_regenerating_keeps_finished_work(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws)

    plan = client.post("/today/plan").json()
    client.post(f"/today/tasks/{plan['tasks'][0]['id']}/complete")

    again = client.post("/today/plan").json()

    assert again["done_tasks"] == 1


def test_skip_ends_the_task(client):
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws)

    plan = client.post("/today/plan").json()
    body = client.post(f"/today/tasks/{plan['tasks'][0]['id']}/skip").json()

    assert body["status"] == "skipped"


def test_unknown_task_returns_404(client):
    assert client.post("/today/tasks/9999/complete").status_code == 404


# --------------------------------
# 미완료 이월
# --------------------------------

def test_unfinished_work_carries_over(client, db_session):
    """어제 못 한 일이 사라지지 않는다."""
    yesterday = date.today() - timedelta(days=1)

    db_session.add(models.DailyPlanTask(
        plan_date=yesterday,
        position=0,
        task_type="project",
        title="어제 못 끝낸 프로젝트",
        minutes=45,
        reason="어제 계획",
        status="planned",
    ))
    db_session.commit()

    body = client.post("/today/plan?available_minutes=120").json()

    titles = [t["title"] for t in body["tasks"]]
    assert "어제 못 끝낸 프로젝트" in titles
    assert body["carried_over"] == 1

    carried = next(t for t in body["tasks"] if t["carried_from"])
    assert carried["carried_from"] == yesterday.isoformat()
    assert "끝내지 못했습니다" in carried["reason"]


def test_skipped_work_does_not_carry_over(client, db_session):
    yesterday = date.today() - timedelta(days=1)

    db_session.add(models.DailyPlanTask(
        plan_date=yesterday,
        position=0,
        task_type="project",
        title="어제 넘긴 것",
        minutes=45,
        status="skipped",
    ))
    db_session.commit()

    body = client.post("/today/plan").json()

    assert "어제 넘긴 것" not in [t["title"] for t in body["tasks"]]


def test_finished_work_does_not_carry_over(client, db_session):
    yesterday = date.today() - timedelta(days=1)

    db_session.add(models.DailyPlanTask(
        plan_date=yesterday,
        position=0,
        task_type="project",
        title="어제 끝낸 것",
        minutes=45,
        status="done",
    ))
    db_session.commit()

    body = client.post("/today/plan").json()

    assert "어제 끝낸 것" not in [t["title"] for t in body["tasks"]]


# --------------------------------
# 서비스 단위
# --------------------------------

def test_allocation_never_exceeds_available_time():
    candidates = [
        {"task_type": "x", "title": "a", "minutes": 90},
        {"task_type": "x", "title": "b", "minutes": 90},
    ]

    chosen, remaining = today_service.allocate(
        candidates, 60, today_service.INTENSITY["normal"]
    )

    assert sum(c["minutes"] for c in chosen) <= 60
    assert remaining >= 0


def test_allocation_skips_blocks_that_are_too_small():
    candidates = [{"task_type": "x", "title": "a", "minutes": 20}]

    chosen, _ = today_service.allocate(
        candidates, 20, today_service.INTENSITY["deep_focus"]
    )

    assert chosen == []


def test_plan_remembers_the_settings_it_was_made_with(client):
    """조회할 때 다른 값을 넘겨도 실제 계획 기준을 따라야 한다.

    안 그러면 60분짜리 계획에 "60분 남음" 같은 틀린 숫자가 나온다.
    """
    aws = _skill(client, "AWS")
    _demand(client, [aws])
    _path_with_step(client, aws, minutes=30)

    client.post("/today/plan?available_minutes=60&intensity=light")

    # 일부러 다른 값으로 조회한다
    body = client.get("/today/plan?available_minutes=180&intensity=deep_focus").json()

    assert body["available_minutes"] == 60
    assert body["intensity"] == "light"
    assert body["remaining_minutes"] == 60 - body["planned_minutes"]


# --------------------------------
# 프로젝트는 스킬 순위를 타지 않는다
#
# 프로젝트를 붙이는 것 자체가 그 스킬의 점수를 낮추기 때문에,
# 전에는 프로젝트를 등록하면 그 프로젝트가 오늘 계획에서 사라졌다.
# --------------------------------

def _proj_skill(client, name, level=0):
    skill = client.post(
        "/skills", json={"name": name, "category": "x", "level": level}
    ).json()

    job = client.post(
        "/jobs", json={"company": "A", "title": f"{name} 공고", "role": "r"}
    ).json()
    client.post(f"/jobs/{job['id']}/skills/{skill['id']}")

    return skill


def _proj_path(client, skill, title):
    path = client.post(
        "/learning-paths",
        json={"title": f"{skill['name']} 배우기", "skill_id": skill["id"]},
    ).json()
    client.post(
        "/learning-steps",
        json={
            "learning_path_id": path["id"],
            "title": title,
            "estimated_minutes": 30,
            "position": 0,
        },
    )


def _proj_make(client, skill, name, **kw):
    payload = {
        "name": name,
        "career_related": True,
        "status": "in_progress",
        "progress_percent": 50,
        "daily_minutes": 45,
    }
    payload.update(kw)

    project = client.post("/projects", json=payload).json()

    if skill is not None:
        client.post(f"/projects/{project['id']}/skills/{skill['id']}")

    return project


def test_a_project_does_not_vanish_by_being_created(client):
    """프로젝트를 붙이면 그 스킬 점수가 반토막 난다.

    전에는 그 때문에 스킬이 1위에서 밀렸고, 후보를 1위 스킬에서만
    뽑았기 때문에 방금 만든 프로젝트가 오늘 계획에 없었다.
    """
    aws = _proj_skill(client, "AWS")
    python = _proj_skill(client, "Python")

    _proj_path(client, aws, "EC2 기초")
    _proj_path(client, python, "Python 기초")

    _proj_make(client, aws, "AWS 배포 프로젝트", progress_percent=60)

    plan = client.post(
        "/today/plan?available_minutes=180&intensity=normal"
    ).json()

    titles = [task["title"] for task in plan["tasks"]]

    # AWS 는 프로젝트 때문에 2위로 내려갔지만 프로젝트는 올라온다.
    assert "AWS 배포 프로젝트" in titles


def test_the_nearly_finished_project_comes_first(client):
    """20% 짜리를 여러 개 벌여두면 증거가 하나도 안 남는다."""
    aws = _proj_skill(client, "AWS")

    _proj_make(client, aws, "거의 끝난 것", progress_percent=85)
    _proj_make(client, aws, "막 시작한 것", progress_percent=10)

    plan = client.post(
        "/today/plan?available_minutes=300&intensity=normal"
    ).json()

    projects = [
        task["title"]
        for task in plan["tasks"]
        if task["task_type"] == "project"
    ]

    assert projects[0] == "거의 끝난 것"


def test_a_project_deadline_beats_progress(client):
    """마감은 되돌릴 수 없다."""
    aws = _proj_skill(client, "AWS")

    _proj_make(client, aws, "거의 끝난 것", progress_percent=90)
    _proj_make(
        client, aws, "마감 임박",
        progress_percent=20, target_date="2020-01-01",
    )

    plan = client.post(
        "/today/plan?available_minutes=300&intensity=normal"
    ).json()

    projects = [
        task["title"]
        for task in plan["tasks"]
        if task["task_type"] == "project"
    ]

    assert projects[0] == "마감 임박"


def test_a_project_with_no_skill_still_counts(client):
    """스킬에 연결되지 않았다고 만들던 것이 사라지면 안 된다."""
    _proj_skill(client, "AWS")
    _proj_make(client, None, "혼자 있는 프로젝트", progress_percent=40)

    plan = client.post(
        "/today/plan?available_minutes=180&intensity=normal"
    ).json()

    assert "혼자 있는 프로젝트" in [t["title"] for t in plan["tasks"]]


def test_a_broken_target_date_does_not_break_the_plan(client):
    """target_date 는 자유 문자열이다. 못 읽으면 없는 셈 친다."""
    aws = _proj_skill(client, "AWS")
    _proj_make(client, aws, "날짜가 이상한 것", target_date="언젠가")

    plan = client.post(
        "/today/plan?available_minutes=180&intensity=normal"
    ).json()

    assert "날짜가 이상한 것" in [t["title"] for t in plan["tasks"]]


def test_today_does_not_fill_up_with_projects(client):
    """하루에 프로젝트를 셋 넣으면 아무것도 안 끝난다."""
    aws = _proj_skill(client, "AWS")

    for index in range(5):
        _proj_make(client, aws, f"프로젝트 {index}", progress_percent=50)

    plan = client.post(
        "/today/plan?available_minutes=600&intensity=normal"
    ).json()

    projects = [t for t in plan["tasks"] if t["task_type"] == "project"]

    assert len(projects) <= 2


def test_an_urgent_opportunity_reaches_todays_plan(client):
    """마감이 내일인 공고를 넣었는데 오늘 계획에 아무것도 없으면 안 된다.

    전에는 마감 후보를 지원서에서만 뽑았다. 그래서 지원서를 아직
    만들지 않은 기회는 D-1 이어도 계획에 올라오지 않았다.
    """
    from datetime import datetime, timedelta

    deadline = (datetime.now() + timedelta(days=1)).isoformat()

    client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "내일 마감 인턴",
            "source": "manual",
            "deadline": deadline,
        },
    )

    plan = client.post(
        "/today/plan?available_minutes=120&intensity=normal"
    ).json()

    first = plan["tasks"][0]

    assert first["task_type"] == "opportunity"
    assert "지원할지 정하기" in first["title"]
    assert first["opportunity_id"] is not None


def test_a_far_opportunity_deadline_does_not_take_over_today(client):
    from datetime import datetime, timedelta

    client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "나중 마감",
            "source": "manual",
            "deadline": (datetime.now() + timedelta(days=10)).isoformat(),
        },
    )

    plan = client.post("/today/plan?available_minutes=120").json()

    assert all(t["task_type"] != "opportunity" for t in plan["tasks"])


def test_the_same_project_is_not_planned_twice(db_session):
    """이월과 신규 후보가 같은 프로젝트를 가리킬 수 있다.

    실제로 났다 — 어제 못 끝낸 프로젝트가 이월로 한 번, "진행 중이니
    오늘도 하라" 는 신규 후보로 또 한 번 올라와 하루 세 칸 중 두 칸을
    같은 일이 차지했다.
    """
    from datetime import date, timedelta

    from app import models
    from app.services import today as today_service

    skill = models.Skill(name="AWS", category="cloud")
    db_session.add(skill)
    db_session.flush()

    project = models.Project(
        name="AWS Deployment Project",
        status="in_progress",
        career_related=True,
        progress_percent=25,
        daily_minutes=45,
    )
    project.skills.append(skill)
    db_session.add(project)
    db_session.flush()

    # 어제 계획했지만 못 끝냈다 → 오늘 이월된다
    db_session.add(
        models.DailyPlanTask(
            plan_date=date.today() - timedelta(days=1),
            position=0,
            task_type="project",
            title=project.name,
            minutes=45,
            reason="어제 계획",
            status="planned",
            project_id=project.id,
        )
    )
    db_session.commit()

    candidates = today_service.build_candidates(db_session, date.today())

    pointing_here = [
        c for c in candidates if c.get("project_id") == project.id
    ]

    assert len(pointing_here) == 1, (
        f"같은 프로젝트가 {len(pointing_here)}번 올라왔습니다"
    )

    # 이월이 먼저다 — 앞쪽이 더 중요한 순서이므로 이월 쪽이 남아야 한다.
    assert "끝내지 못했습니다" in pointing_here[0]["reason"]


def test_a_posting_with_an_application_is_listed_once(db_session):
    """같은 공고가 마감 띠에 두 줄로 뜨면 안 된다.

    지원서를 만들기 전에는 기회로만 떴다. 만들고 나니 지원서로도
    뜨면서 "인공지능 (AI부문)" 이 D-5 로 두 번 나왔고, 오늘 계획에도
    "지원 준비" 와 "지원할지 정하기" 가 각각 한 칸씩 차지했다.

    지원서가 더 진행된 상태이므로 그쪽을 남긴다.
    """
    from datetime import date, datetime, timedelta

    from app import models
    from app.services import today as today_service

    # 긴급 구간 안에 둔다. 그 바깥이면 후보 자체가 안 만들어져서
    # 중복을 확인할 수 없다.
    deadline = datetime.now() + timedelta(
        days=today_service.DEADLINE_URGENT_DAYS
    )

    opportunity = models.Opportunity(
        title="인공지능 (AI부문)", organization="어떤회사",
        opportunity_type="job", source="manual",
        status="interested", deadline=deadline,
    )
    db_session.add(opportunity)
    db_session.flush()

    db_session.add(models.Application(
        opportunity_id=opportunity.id,
        status="preparing",
        deadline=deadline,
    ))
    db_session.commit()

    items = today_service.collect_deadlines(db_session, date.today())

    assert len(items) == 1
    assert items[0]["kind"] == "application"

    # 오늘 계획에도 한 칸만
    candidates = today_service.build_candidates(db_session, date.today())
    about_it = [c for c in candidates if "인공지능" in c["title"]]

    assert len(about_it) == 1
    assert about_it[0]["title"].startswith("지원 준비")


def test_a_posting_without_an_application_still_shows(db_session):
    """지원서가 없으면 기회로 떠야 한다. 그게 원래 고친 버그다."""
    from datetime import date, datetime, timedelta

    from app import models
    from app.services import today as today_service

    db_session.add(models.Opportunity(
        title="지원서 없는 공고", organization="어떤회사",
        opportunity_type="job", source="manual", status="interested",
        deadline=datetime.now() + timedelta(days=2),
    ))
    db_session.commit()

    items = today_service.collect_deadlines(db_session, date.today())

    assert len(items) == 1
    assert items[0]["kind"] == "opportunity"


def test_a_withdrawn_application_does_not_bring_the_posting_back(db_session):
    """DX 지원을 접었는데 같은 공고가 "공고 마감" 으로 다시 떴다.

    철회한 지원서는 마감 목록에서 빠지지만, 그 공고를 덮는 것까지
    빠지면 안 된다. 이미 정한 공고다."""
    from datetime import date, datetime, timedelta

    from app import models
    from app.services import today as today_service

    deadline = datetime.now() + timedelta(days=1)
    posting = models.Opportunity(
        title="인공지능 (AI부문)", organization="한빛전자",
        opportunity_type="job", source="manual", status="interested",
        deadline=deadline,
    )
    db_session.add(posting)
    db_session.flush()
    db_session.add(models.Application(
        opportunity_id=posting.id, status="withdrawn", deadline=deadline,
    ))
    db_session.commit()

    assert today_service.collect_deadlines(db_session, date.today()) == []


def _skill_with_resources(db):
    from app import models

    skill = models.Skill(name="SQL", category="data")
    db.add(skill)
    db.flush()

    # 먼저 등록된 것: 분량을 모르는 책
    book = models.LearningResource(
        title="분량 모르는 책", resource_type="book",
        duration_minutes=0, ownership="owned", skill_id=skill.id,
    )

    # 나중에 등록된 것: 챕터로 쪼갠 강좌
    course = models.LearningResource(
        title="쪼개둔 강좌", resource_type="video",
        duration_minutes=173, ownership="saved", skill_id=skill.id,
    )

    db.add_all([book, course])
    db.flush()

    db.add(models.LearningResourceSegment(
        learning_resource_id=course.id, position=0,
        label="0:00 인트로", start_ref=0, end_ref=687,
        estimated_minutes=11,
    ))
    db.commit()

    return skill


def test_a_split_resource_wins_over_one_we_cannot_measure(db_session):
    """쪼개는 일이 계획에 반영되지 않으면 쪼갤 이유가 없다.

    전에는 skill.resources[0] 을 그냥 집었다. 그래서 13챕터로
    쪼개둔 강좌를 두고, 분량도 모르는 책이 먼저 등록됐다는 이유로
    "30분" 이라는 지어낸 숫자를 내놓았다.
    """
    from app.services import today as today_service

    skill = _skill_with_resources(db_session)

    candidate = today_service._learning_candidate(
        db_session, {"skill": skill, "priority_score": 400}
    )

    assert "쪼개둔 강좌" in candidate["title"]
    assert "인트로" in candidate["title"]
    assert candidate["minutes"] == 11


def test_a_known_length_beats_an_unknown_one(db_session):
    """쪼갠 게 하나도 없으면, 적어도 길이를 아는 쪽을 고른다."""
    from app import models
    from app.services import today as today_service

    skill = models.Skill(name="Python", category="lang")
    db_session.add(skill)
    db_session.flush()

    db_session.add_all([
        models.LearningResource(
            title="분량 모르는 것", resource_type="book",
            duration_minutes=0, ownership="owned", skill_id=skill.id,
        ),
        models.LearningResource(
            title="27분짜리", resource_type="video",
            duration_minutes=27, ownership="saved", skill_id=skill.id,
        ),
    ])
    db_session.commit()

    candidate = today_service._learning_candidate(
        db_session, {"skill": skill, "priority_score": 100}
    )

    assert candidate["title"] == "27분짜리"
    assert candidate["minutes"] == 27
