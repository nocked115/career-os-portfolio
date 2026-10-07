

def test_a_practice_project_is_planned_but_not_counted_as_evidence(client, db_session):
    """수업 과제는 오늘 할 일이지만 커리어 증거는 아니다.

    증거로 세면 "과제를 했으니 그 스킬은 덜 급하다" 가 되는데, 정작 포트폴리오에
    보여줄 것은 없다.
    """
    from datetime import date, timedelta

    from app import models
    from app.services import priority as priority_service
    from app.services import today as today_service

    skill = models.Skill(name="추천시스템", category="ai", level=1)
    db_session.add(skill)
    db_session.flush()

    practice = models.Project(
        name="추천시스템 수업 과제", status="in_progress", career_related=True,
        purpose="practice", progress_percent=50, daily_minutes=30,
        target_date=(date.today() + timedelta(days=5)).isoformat(),
    )
    hobby = models.Project(
        name="취미 게임", status="in_progress", career_related=True,
        purpose="hobby", progress_percent=10, daily_minutes=30,
    )
    db_session.add_all([practice, hobby])
    db_session.flush()
    practice.skills.append(skill)
    db_session.commit()

    assert priority_service.project_evidence_strength(practice) == 0.0

    titles = [
        candidate["title"]
        for candidate in today_service.build_candidates(db_session, date.today())
    ]

    assert any("추천시스템 수업 과제" in title for title in titles)
    assert not any("취미 게임" in title for title in titles)


def test_purpose_defaults_to_evidence(client):
    made = client.post("/projects", json={"name": "심화 프로젝트"}).json()

    assert made["purpose"] == "evidence"
    assert client.patch(
        f"/projects/{made['id']}", json={"purpose": "practice"}
    ).json()["purpose"] == "practice"
