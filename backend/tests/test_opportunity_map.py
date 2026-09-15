"""공고 하나를 기준으로 펼친 지도.

칸은 이미 다 있었다. 지도는 새로 계산하지 않고 선만 잇는다.
각 스킬이 어디까지 찼는지는 셀 수 있는 것으로만 정한다.
"""

from datetime import datetime, timedelta

from app import models
from app.services import opportunity_map


def _world(db):
    ml = models.Skill(name="Machine Learning", category="ai")
    nlp = models.Skill(name="NLP", category="ai")
    sql = models.Skill(name="SQL", category="data", level=2)
    da = models.Skill(name="Data Analysis", category="data")
    db.add_all([ml, nlp, sql, da])
    db.flush()

    opp = models.Opportunity(
        title="인공지능", organization="어떤회사", opportunity_type="job",
        source="manual", source_url="https://example.com/1",
        deadline=datetime.now() + timedelta(days=5),
    )
    opp.skills.extend([ml, nlp, sql, da])
    db.add(opp)

    # ML: 책을 쪼갰고 1장 끝냄 → 공부 중
    book = models.LearningResource(
        title="핸즈온 머신러닝", resource_type="book", ownership="owned",
        skill_id=ml.id,
    )
    db.add(book)
    db.flush()
    db.add_all([
        models.LearningResourceSegment(
            learning_resource_id=book.id, position=0, label="1장",
            estimated_minutes=45, status="completed",
            completed_at=datetime.now(),
        ),
        models.LearningResourceSegment(
            learning_resource_id=book.id, position=1, label="2장",
            estimated_minutes=45,
        ),
    ])

    # Data Analysis: 프로젝트와 경험까지 → 쓸 수 있음
    project = models.Project(name="분석 프로젝트", status="completed",
                             career_related=True, progress_percent=100)
    project.skills.append(da)
    exp = models.Experience(experience_type="project", title="Netflix 분석")
    exp.skills.append(da)
    db.add_all([project, exp])

    db.commit()
    return opp


def _row(result, name):
    return next(r for r in result["skills"] if r["skill"] == name)


def test_each_skill_gets_the_stage_it_has_earned(db_session):
    result = opportunity_map.build_map(db_session, _world(db_session))

    assert _row(result, "Data Analysis")["stage"] == "covered"
    assert _row(result, "Machine Learning")["stage"] == "studying"
    assert _row(result, "SQL")["stage"] == "studying"      # 레벨이 있다
    assert _row(result, "NLP")["stage"] == "empty"


def test_study_counts_come_from_real_segments(db_session):
    ml = _row(
        opportunity_map.build_map(db_session, _world(db_session)),
        "Machine Learning",
    )

    assert ml["study"]["units_done"] == 1
    assert ml["study"]["units_total"] == 2
    # 다음 할 일은 끝낸 1장이 아니라 2장
    assert "2장" in ml["study"]["next"]


def test_evidence_is_listed_by_name(db_session):
    da = _row(opportunity_map.build_map(db_session, _world(db_session)),
              "Data Analysis")

    assert [p["name"] for p in da["projects"]] == ["분석 프로젝트"]
    assert [e["title"] for e in da["experiences"]] == ["Netflix 분석"]


def test_summary_counts_the_gaps(db_session):
    summary = opportunity_map.build_map(db_session, _world(db_session))["summary"]

    assert summary == {"total": 4, "covered": 1, "building": 0,
                       "studying": 2, "empty": 1}


def test_unrelated_side_projects_are_not_evidence(db_session):
    """커리어와 무관한 프로젝트를 증거로 세면 칸이 거짓으로 찬다."""
    opp = _world(db_session)
    nlp = db_session.query(models.Skill).filter_by(name="NLP").one()

    side = models.Project(name="사이버덱", status="in_progress",
                          career_related=False)
    side.skills.append(nlp)
    db_session.add(side)
    db_session.commit()

    assert _row(opportunity_map.build_map(db_session, opp), "NLP")["stage"] == "empty"


def test_endpoint(client, db_session):
    opp = _world(db_session)

    body = client.get(f"/opportunities/{opp.id}/map").json()

    assert body["opportunity"]["title"] == "인공지능"
    assert body["opportunity"]["status"] == "discovered"
    assert body["opportunity"]["days_left"] in (4, 5)
    assert len(body["skills"]) == 4
    assert client.get("/opportunities/99999/map").status_code == 404
