"""학습 우선순위 계산 - Mission 021 에서 통합한 단일 로직 검증."""

from app.agents import tools
from app.services import priority


def test_skill_gap_never_negative():
    """MAX_SKILL_LEVEL 을 넘는 레벨에서도 음수가 나오면 안 된다.

    통합 전 /analytics/learning-priority 는 max(0, ...) 가드가 없어서
    레벨이 상한을 넘으면 우선순위 점수가 음수로 나왔다.
    """
    assert priority.calculate_skill_gap(0) == 4
    assert priority.calculate_skill_gap(4) == 0
    assert priority.calculate_skill_gap(9) == 0


def test_market_percentage_handles_zero_jobs():
    assert priority.calculate_market_percentage(0, 0) == 0
    assert priority.calculate_market_percentage(3, 0) == 0
    assert priority.calculate_market_percentage(1, 4) == 25


def test_a_finished_project_halves_the_score(
    db_session, seed_skill, seed_job, seed_project
):
    """만들어낸 것이 있으면 그 스킬을 새로 배울 필요는 줄어든다."""
    with_evidence = seed_skill("AWS", level=1)
    without_evidence = seed_skill("SQL", level=1)

    seed_job(skills=[with_evidence, without_evidence])
    seed_project(
        "AWS Deployment",
        skills=[with_evidence],
        status="completed",
        progress_percent=100,
    )

    entries = {
        entry["skill_name"]: entry
        for entry in priority.build_skill_priorities(db_session)
    }

    assert entries["AWS"]["evidence_weight"] == 0.5
    assert entries["SQL"]["evidence_weight"] == 1.0
    assert entries["AWS"]["priority_score"] == 150
    assert entries["SQL"]["priority_score"] == 300


def test_an_empty_project_is_not_evidence_yet(
    db_session, seed_skill, seed_job, seed_project
):
    """프로젝트가 있다는 사실과 그것이 증거라는 사실은 다르다.

    전에는 career_related 하나만 봐서, 0% 짜리 빈 프로젝트를 만들기만
    해도 우선순위가 반토막 났다. 만들기로 마음먹은 것과 만들어낸 것을
    같게 치면 안 된다.
    """
    skill = seed_skill("AWS", level=1)
    seed_job(skills=[skill])
    seed_project(
        "AWS Deployment",
        skills=[skill],
        status="planned",
        progress_percent=0,
    )

    entry = priority.build_skill_priorities(db_session)[0]

    assert entry["evidence_strength"] == priority.PROJECT_EVIDENCE["started"]
    assert entry["priority_score"] == 270      # 절반(150)이 아니다


def test_evidence_grows_as_the_project_goes_further(
    db_session, seed_skill, seed_job, seed_project
):
    """계획 → 진행 → 완료 → 보여줄 수 있음 순으로 증거가 세진다."""
    strengths = []

    for status, progress, extra in (
        ("planned", 0, {}),
        ("in_progress", 40, {}),
        ("completed", 100, {}),
        ("completed", 100, {"github_url": "https://example.com"}),
    ):
        project = seed_project(
            f"P-{status}-{progress}-{len(extra)}",
            status=status,
            progress_percent=progress,
            **extra,
        )
        strengths.append(priority.project_evidence_strength(project))

    assert strengths == sorted(strengths)
    assert len(set(strengths)) == len(strengths)


def test_showing_nothing_is_weaker_than_showing_something(
    db_session, seed_skill, seed_job, seed_project
):
    """끝났는데 GitHub·데모·결과가 하나도 없으면 완전한 증거가 아니다."""
    hidden = seed_project(
        "보여줄 것 없음", status="completed", progress_percent=100
    )
    shown = seed_project(
        "결과 있음",
        status="completed",
        progress_percent=100,
        results="배포 시간 30분 → 5분",
    )

    assert priority.project_evidence_strength(
        hidden
    ) < priority.project_evidence_strength(shown)


def test_evidence_never_zeroes_out_the_priority(
    db_session, seed_skill, seed_job, seed_project
):
    """다 아는 것처럼 보여도 시장은 계속 움직인다."""
    assert priority.combine_evidence(0.85, 0.4) <= (
        1.0 - priority.EVIDENCE_WEIGHT_FLOOR
    )


def test_non_career_project_is_not_evidence(
    db_session, seed_skill, seed_job, seed_project
):
    skill = seed_skill("Docker", level=1)
    seed_job(skills=[skill])
    seed_project("취미 프로젝트", skills=[skill], career_related=False)

    entry = priority.build_skill_priorities(db_session)[0]

    assert entry["has_project_evidence"] is False
    assert entry["evidence_weight"] == 1.0


def test_results_are_sorted_by_score(
    db_session, seed_skill, seed_job
):
    low = seed_skill("Low", level=3)
    high = seed_skill("High", level=0)

    seed_job(skills=[low, high])

    scores = [
        entry["priority_score"]
        for entry in priority.build_skill_priorities(db_session)
    ]

    assert scores == sorted(scores, reverse=True)


def test_agent_and_api_report_the_same_score(
    db_session, seed_skill, seed_job, seed_project
):
    """통합 전에는 tools.py 가 evidence_weight 를 빼먹어서
    Agent 응답과 API 응답의 점수가 서로 달랐다."""
    skill = seed_skill("AWS", level=1)
    seed_job(skills=[skill])
    seed_project(
        "AWS Deployment",
        skills=[skill],
        status="completed",
        progress_percent=100,
    )

    from_agent = tools.get_learning_priority(db_session)
    from_api = priority.get_learning_priority(db_session)

    assert from_agent == from_api
    assert from_agent[0]["priority_score"] == 150


def test_serialized_output_has_no_orm_objects(
    db_session, seed_skill, seed_job
):
    """API 응답에 ORM 객체가 새어나가면 직렬화가 깨진다."""
    skill = seed_skill("Python", level=2)
    seed_job(skills=[skill])

    item = priority.get_learning_priority(
        db_session,
        include_resources=True,
    )[0]

    assert item["skill"] == "Python"
    assert item["career_projects"] == []
    assert item["resources"] == []
    assert all(not hasattr(v, "__table__") for v in item.values())


def test_promoting_to_experience_alone_is_not_the_top_rung(
    db_session, seed_skill, seed_job, seed_project
):
    """Experience 로 옮기는 건 클릭 한 번이다.

    그것만으로 GitHub 저장소 하나보다 더 증명하지는 못한다.
    최고 등급은 보여줄 것이 있고 정리까지 된 경우다.
    """
    project = seed_project(
        "AWS Deployment", status="completed", progress_percent=100
    )

    bookkeeping_only = priority.project_evidence_strength(
        project, has_experience=True
    )
    assert bookkeeping_only == priority.PROJECT_EVIDENCE["shown"]

    project.github_url = "https://github.com/x/y"
    db_session.commit()

    both = priority.project_evidence_strength(project, has_experience=True)
    assert both == priority.PROJECT_EVIDENCE["used"]


def test_priority_payload_carries_the_skill_id(db_session):
    """화면이 레벨을 고치려면 무엇을 고칠지 알아야 한다.

    이름만으로는 PATCH 할 대상을 찾을 수 없다. 지금까지 나온
    응답 필드 누락과 같은 종류다.
    """
    from app import models
    from app.services import priority

    skill = models.Skill(name="Machine Learning", category="ai")
    db_session.add(skill)
    db_session.commit()

    rows = priority.build_skill_priorities(db_session)
    payload = priority.serialize_priority(rows[0])

    assert payload["skill_id"] == skill.id
