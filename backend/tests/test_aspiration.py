"""지금은 지원 못 하는 자리가 요구하는 것 — 목표표.

수현: "지원 자격이 안 되는 그거, 넣으면 좀 지우고 거기서 요구 역량만
뽑아서 참고자료로 쓰던가 해. 내가 가진 프로젝트나 이런 거랑 합치면
되겠네."

지원 못 하는 자리야말로 가고 싶은 자리다. 목록에서 내리는 것까지는
이미 하는데, 내리고 나면 요구사항도 같이 사라지던 것이 문제였다.
"""

from app import models
from app.services import aspiration, tidy


def _posting(db, title, skills=(), description="", blocked="",
             org="KRAFTON", kind="job"):
    row = models.Opportunity(
        opportunity_type=kind, title=title, organization=org,
        source="manual", description=description, status="discovered",
        blocked_reason=blocked,
    )
    row.skills.extend(skills)
    db.add(row)
    db.commit()
    return row


def _skill(db, name, level=0):
    skill = models.Skill(name=name, category="ml", level=level)
    db.add(skill)
    db.commit()
    return skill


def test_nothing_blocked_means_an_empty_sheet(db_session):
    _posting(db_session, "데이터 엔지니어")

    assert aspiration.build(db_session)["postings"] == 0


def test_it_lists_the_conditions_in_the_postings_own_words(db_session):
    _posting(
        db_session, "Research Scientist",
        description="자격요건\n딥러닝 관련 분야 석/박사 졸업 이상\n유관 업무 경험 5년 이상이신 분",
        blocked="석박사 요건",
    )

    sheet = aspiration.build(db_session)

    kinds = [row["kind"] for row in sheet["conditions"]]
    assert kinds == ["degree", "career"]          # 학력이 먼저
    assert "석/박사 졸업 이상" in sheet["conditions"][0]["lines"][0]


def test_a_summary_line_is_not_a_requirement(db_session):
    """수집기가 글 맨 위에 붙이는 "맞는 이유: … (2년 이상 / 인턴)" 이
    경력 요건으로 잡혔다. 공고가 요구한 게 아니라 요약에 쓰인 말이다."""
    _posting(
        db_session, "AI Companion Team Intern",
        description="맞는 이유: [AI Research Div.] Internship (2년 이상 / 인턴)\n우리 팀을 소개합니다",
        blocked="석박사 요건",
    )

    assert aspiration.build(db_session)["conditions"] == []


def test_the_skills_come_with_my_own_projects(db_session):
    """목록만 주면 "이만큼 모자라다" 로만 읽힌다. 가진 것이 같이 보여야
    무엇을 더할지가 보인다."""
    pytorch = _skill(db_session, "PyTorch", level=2)
    rl = _skill(db_session, "Reinforcement Learning")

    project = models.Project(name="의료영상 이상탐지", status="completed")
    project.skills.append(pytorch)
    db_session.add(project)
    db_session.commit()

    _posting(db_session, "Research Scientist", skills=[pytorch, rl],
             blocked="석박사 요건")

    rows = {row["skill"]: row for row in aspiration.build(db_session)["skills"]}

    assert rows["PyTorch"]["standing"] == "proven"
    assert rows["PyTorch"]["projects"][0]["title"] == "의료영상 이상탐지"
    assert rows["Reinforcement Learning"]["standing"] == "missing"
    assert rows["Reinforcement Learning"]["projects"] == []


def test_a_skill_i_am_learning_is_not_called_missing(db_session):
    skill = _skill(db_session, "Vision-Language", level=1)
    _posting(db_session, "Research Engineer", skills=[skill], blocked="석박사 요건")

    row = aspiration.build(db_session)["skills"][0]

    assert row["standing"] == "learning"
    assert row["my_level"] == 1


def test_an_out_of_town_job_fair_is_not_an_aspiration(db_session):
    """치우기가 서울 밖 행사에도 blocked_reason 을 적는다. 그건 못 가는
    자리가 아니라 안 가는 행사다 — 섞으면 목표표에 박람회가 올라온다."""
    skill = _skill(db_session, "Deep Learning")
    _posting(db_session, "부산 채용박람회", skills=[skill],
             blocked=tidy.FAR_REASON, kind="job_event", org="부산테크노파크")
    _posting(db_session, "Research Scientist", skills=[skill], blocked="석박사 요건")

    sheet = aspiration.build(db_session)

    assert sheet["postings"] == 1
    assert sheet["skills"][0]["asked_by"] == 1


def test_the_most_demanded_comes_first_and_gaps_outrank_proven(db_session):
    """같은 횟수면 증거 없는 쪽을 위로 — 그게 할 일이다."""
    proven = _skill(db_session, "Python")
    missing = _skill(db_session, "Airflow")

    project = models.Project(name="Career OS", status="in_progress")
    project.skills.append(proven)
    db_session.add(project)
    db_session.commit()

    _posting(db_session, "A", skills=[proven, missing], blocked="석박사 요건")

    names = [row["skill"] for row in aspiration.build(db_session)["skills"]]

    assert names == ["Airflow", "Python"]
