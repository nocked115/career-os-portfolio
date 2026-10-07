"""로드맵 한 장을 통째로 들여온다.

수현: "한 스킬이 지금 중요하다 하면 전체적인 roadmap 짜기 이런 게 있어야
하지 않을까, 그래야 포트폴리오에 쓸 만한 end-to-end 프로젝트가 나오지."

그리고: "시간당 나눴을 때 오늘은 전체 주차에서 이만큼 하겠다가 있어야
하는 거 아닌가."
"""

from datetime import date, timedelta

import pytest

from app import models
from app.services import roadmap


ROADMAP = """
# 경로: 데이터 파이프라인 — 신입 포트폴리오용
목표: 공고 20/71건이 요구. 레벨 0 → 2
목표일: 2026-12-20

## 1주차 · SQL 로 원천 데이터 다루기 (180분)
- 윈도우 함수로 집계 쿼리 쓰기
- 조인 성능 확인하기

## 2주차 · Airflow 로 돌리기 (1시간 30분)
- DAG 하나 만들기

## 최종 프로젝트: 공고 수집 → 정제 → BigQuery 적재 → 대시보드
증명: 데이터 파이프라인, SQL, BigQuery
남길 것: GitHub, 데모 링크
하루 한 번 돌아가는 파이프라인을 만든다.
"""


def test_a_roadmap_becomes_a_path_with_steps_and_checks(client, db_session):
    body = client.post(
        "/learning-paths/import-roadmap", json={"text": ROADMAP}
    ).json()

    assert body["steps"] == 2
    assert body["checklist_items"] == 3
    assert body["total_minutes"] == 180 + 90

    path = db_session.get(models.LearningPath, body["learning_path_id"])
    assert path.title == "데이터 파이프라인 — 신입 포트폴리오용"
    assert path.target_date == date(2026, 12, 20)

    # 주차 표기는 제목에 남긴다. 기존 경로도 "3주차 · 협업 필터링 기본" 꼴이다.
    steps = sorted(path.steps, key=lambda s: s.position)
    assert [s.title for s in steps] == [
        "1주차 · SQL 로 원천 데이터 다루기", "2주차 · Airflow 로 돌리기"
    ]
    assert [s.estimated_minutes for s in steps] == [180, 90]


def test_the_last_block_becomes_a_real_project(client, db_session):
    """주제만 늘어놓으면 다 해도 포트폴리오에 쓸 게 안 남는다."""
    db_session.add(models.Skill(name="SQL", category="data", level=0))
    db_session.add(models.Skill(name="BigQuery", category="data", level=0))
    db_session.commit()

    body = client.post(
        "/learning-paths/import-roadmap", json={"text": ROADMAP}
    ).json()

    project = db_session.get(models.Project, body["project_id"])

    assert project.name.startswith("공고 수집")
    # 증거로 남기려고 하는 것이다. 취미가 아니다.
    assert project.purpose == "evidence"
    assert "파이프라인" in project.description

    # 있는 스킬만 잇는다. 없는 이름("데이터 파이프라인")은 만들지 않는다.
    assert {s.name for s in project.skills} == {"SQL", "BigQuery"}


def test_the_new_project_is_judged_by_the_existing_evidence_rules(client, db_session):
    """판단하는 쪽을 새로 만들지 않고 이미 있는 데로 꽂는다."""
    from app.services import proof

    db_session.add(models.Skill(name="SQL", category="data", level=0))
    db_session.commit()

    body = client.post(
        "/learning-paths/import-roadmap", json={"text": ROADMAP}
    ).json()

    project = db_session.get(models.Project, body["project_id"])
    suggestions = proof.build_suggestions(db_session, project)

    # 아직 시작 전이라 "완료하면 증거로 만들 수 있다" 를 말한다.
    assert suggestions["is_complete"] is False
    assert {"결과 기록", "GitHub 링크 추가", "데모 링크 추가"} <= {
        action["label"] for action in suggestions["actions"]
    }


def test_a_roadmap_without_a_project_says_so(client):
    text = "# 경로: 그냥 공부\n\n## 1주차 · 읽기 (60분)\n- 읽기\n"

    body = client.post("/learning-paths/parse-roadmap", json={"text": text}).json()

    assert body["project"] is None
    assert any("포트폴리오" in w for w in body["warnings"])


def test_a_roadmap_without_times_says_so(client):
    text = "# 경로: 시간 없음\n\n## 1주차 · 읽기\n- 읽기\n\n## 최종 프로젝트: 뭔가\n"

    body = client.post("/learning-paths/parse-roadmap", json={"text": text}).json()

    assert body["total_minutes"] == 0
    assert any("오늘 할 몫" in w for w in body["warnings"])


def test_an_unreadable_roadmap_says_what_is_missing(client):
    assert client.post(
        "/learning-paths/parse-roadmap", json={"text": "그냥 줄글입니다"}
    ).status_code == 422

    assert client.post(
        "/learning-paths/parse-roadmap", json={"text": "# 경로: 제목만 있음"}
    ).status_code == 422


def test_parsing_does_not_save(client, db_session):
    before = db_session.query(models.LearningPath).count()

    client.post("/learning-paths/parse-roadmap", json={"text": ROADMAP})

    assert db_session.query(models.LearningPath).count() == before


# --------------------------------
# 오늘 할 몫
# --------------------------------

def _path_with(db, minutes, target_days, done=0):
    path = models.LearningPath(title="경로", target_date=date.today() + timedelta(days=target_days))
    db.add(path)
    db.flush()

    for position, amount in enumerate(minutes):
        db.add(models.LearningStep(
            learning_path_id=path.id, title=f"{position + 1}주차",
            position=position, estimated_minutes=amount,
            status="completed" if position < done else "not_started",
        ))

    db.commit()
    db.refresh(path)
    return path


def test_today_is_the_remaining_time_divided_by_the_remaining_days(db_session):
    """로드맵에 24시간이라고 적혀 있어도 오늘 몇 분인지 안 나오면 계획이 안 된다."""
    path = _path_with(db_session, [180, 180, 180], target_days=9)

    result = roadmap.pace(path)

    assert result["total_minutes"] == 540
    assert result["left_minutes"] == 540
    assert result["days_left"] == 9
    assert result["minutes_per_day"] == 60


def test_finished_steps_come_off_the_remaining_time(db_session):
    path = _path_with(db_session, [180, 180, 180], target_days=9, done=2)

    result = roadmap.pace(path)

    assert result["done_minutes"] == 360
    assert result["left_minutes"] == 180
    assert result["minutes_per_day"] == 20
    assert result["current_step"]["title"] == "3주차"


def test_without_a_target_date_nothing_is_divided(db_session):
    """지어낸 날짜로 나눈 숫자는 어디서 왔는지 설명할 수 없다."""
    path = models.LearningPath(title="마감 없음")
    db_session.add(path)
    db_session.flush()
    db_session.add(models.LearningStep(
        learning_path_id=path.id, title="1주차", position=0, estimated_minutes=120,
    ))
    db_session.commit()
    db_session.refresh(path)

    result = roadmap.pace(path)

    assert result["days_left"] is None
    assert result["minutes_per_day"] is None
    assert result["left_minutes"] == 120


def test_a_deadline_today_does_not_divide_by_zero(db_session):
    path = _path_with(db_session, [120], target_days=0)

    assert roadmap.pace(path)["minutes_per_day"] == 120


def test_an_impossible_pace_is_flagged(db_session):
    """하루 3시간을 넘기면 일정이 빡빡하다는 뜻이다."""
    assert roadmap.pace(_path_with(db_session, [600, 600], target_days=3))["behind"] is True
    assert roadmap.pace(_path_with(db_session, [60], target_days=30))["behind"] is False


def test_the_pace_endpoint(client, db_session):
    path = _path_with(db_session, [180, 180], target_days=6)

    body = client.get(f"/learning-paths/{path.id}/pace").json()

    assert body["minutes_per_day"] == 60
    assert body["total_steps"] == 2


# --------------------------------
# 구간별 속도
# --------------------------------

def _path_with_milestones(db):
    """수현의 #10 과 같은 모양 — 마감이 중간에 둘, 경로 목표일이 따로."""
    path = models.LearningPath(
        title="Hands-On ML", target_date=date.today() + timedelta(days=145),
    )
    db.add(path)
    db.flush()

    plan = [
        (180, None), (540, None), (360, None), (540, None), (1080, None),
        (720, date.today() + timedelta(days=65)),      # ML Core 마감
        (720, None), (1440, None), (420, None), (2280, None),
        (1380, date.today() + timedelta(days=117)),    # 프로젝트 마감
    ]

    for position, (minutes, due) in enumerate(plan):
        db.add(models.LearningStep(
            learning_path_id=path.id, title=f"{position + 1}단계",
            position=position, estimated_minutes=minutes, due_date=due,
        ))

    db.commit()
    db.refresh(path)
    return path


def test_the_pace_follows_the_next_milestone_not_the_far_target(db_session):
    """161시간을 2/28 까지로 고르게 나누면 하루 1시간 7분이 나오는데,
    정작 12/10 까지 끝내야 할 57시간은 하루 53분이다."""
    path = _path_with_milestones(db_session)

    result = roadmap.pace(path)

    # 전체는 여전히 전체대로
    assert result["total_minutes"] == 9660
    assert result["minutes_per_day"] == round(9660 / 145)

    # 지금 달려야 할 속도는 다음 마감까지의 것
    segment = result["segment"]
    assert segment["left_minutes"] == 180 + 540 + 360 + 540 + 1080 + 720   # 3420
    assert segment["days_left"] == 65
    assert segment["minutes_per_day"] == round(3420 / 65)                  # 53
    assert segment["overdue"] is False


def test_finished_steps_come_off_the_segment(db_session):
    path = _path_with_milestones(db_session)
    steps = sorted(path.steps, key=lambda s: s.position)

    for step in steps[:3]:
        step.status = "completed"
    db_session.commit()

    segment = roadmap.pace(path)["segment"]

    assert segment["left_minutes"] == 540 + 1080 + 720


def test_the_segment_moves_on_when_the_milestone_is_done(db_session):
    """12/10 이 지나면 다음 구간(1/31)으로 저절로 넘어간다."""
    path = _path_with_milestones(db_session)
    steps = sorted(path.steps, key=lambda s: s.position)

    for step in steps[:6]:
        step.status = "completed"
    db_session.commit()

    segment = roadmap.pace(path)["segment"]

    assert segment["title"] == "11단계"
    assert segment["days_left"] == 117


def test_an_overdue_milestone_says_so(db_session):
    """숫자를 내밀기 전에 지났다는 말을 먼저 해야 한다."""
    path = models.LearningPath(title="늦음")
    db_session.add(path)
    db_session.flush()
    db_session.add(models.LearningStep(
        learning_path_id=path.id, title="1단계", position=0,
        estimated_minutes=600, due_date=date.today() - timedelta(days=5),
    ))
    db_session.commit()
    db_session.refresh(path)

    assert roadmap.pace(path)["segment"]["overdue"] is True


def test_without_milestones_there_is_no_segment(db_session):
    path = _path_with(db_session, [120, 120], target_days=30)

    assert roadmap.pace(path)["segment"] is None
