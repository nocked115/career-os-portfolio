"""내보내기 / 불러오기.

행 개수만 맞는지 보면 의미가 없다. 이 기능의 목적은 관계를
살려서 옮기는 것이므로, 연결 테이블과 외래키가 살아남는지를 본다.
"""

import pytest

from app import models
from app.services import transfer as transfer_service


def _populate(db):
    """스킬 - 기회 - 지원서까지 이어진 작은 세계를 만든다."""
    skill = models.Skill(name="PyTorch", category="ml", level=40)
    other = models.Skill(name="Kubernetes", category="infra", level=10)

    db.add_all([skill, other])
    db.flush()

    opportunity = models.Opportunity(
        title="ML Engineer",
        organization="어떤회사",
        opportunity_type="job",
        source="manual",
        status="interested",
    )

    opportunity.skills.append(skill)

    db.add(opportunity)
    db.flush()

    application = models.Application(
        opportunity_id=opportunity.id,
        status="preparing",
    )

    db.add(application)
    db.commit()

    return skill, opportunity, application


def test_round_trip_keeps_links_between_tables(db_session):
    skill, opportunity, application = _populate(db_session)

    skill_id = skill.id
    opportunity_id = opportunity.id
    application_id = application.id

    payload = transfer_service.dump(db_session)

    # 전부 지운 것처럼 만든 다음 되돌린다.
    db_session.query(models.Application).delete()
    db_session.query(models.Opportunity).delete()
    db_session.query(models.Skill).delete()
    db_session.commit()

    assert db_session.query(models.Skill).count() == 0

    transfer_service.load(db_session, payload)

    restored = db_session.get(models.Opportunity, opportunity_id)

    assert restored is not None
    assert restored.title == "ML Engineer"

    # 연결 테이블 — 이게 살아야 옮긴 의미가 있다.
    assert [s.id for s in restored.skills] == [skill_id]

    # 외래키
    restored_application = db_session.get(models.Application, application_id)

    assert restored_application.opportunity_id == opportunity_id


def test_import_replaces_rather_than_merges(db_session):
    _populate(db_session)

    payload = transfer_service.dump(db_session)

    # 파일에 없는 것을 하나 더 만들어 둔다.
    db_session.add(
        models.Skill(name="Rust", category="lang", level=0)
    )
    db_session.commit()

    result = transfer_service.load(db_session, payload)

    names = {s.name for s in db_session.query(models.Skill).all()}

    # 합치면 Rust 가 남는다. 대체하면 사라진다.
    assert "Rust" not in names
    assert names == {"PyTorch", "Kubernetes"}
    assert result["replaced"]["skills"] == 3
    assert result["written"]["skills"] == 2


def test_datetimes_come_back_as_datetimes_not_strings(db_session):
    """JSON 에는 날짜가 없다. 문자열로 돌아오면 마감 계산에서 터진다."""
    from datetime import datetime

    when = datetime(2026, 12, 31, 18, 0)

    db_session.add(
        models.Opportunity(
            title="마감 있는 것",
            organization="어떤회사",
            opportunity_type="job",
            source="manual",
            deadline=when,
        )
    )
    db_session.commit()

    payload = transfer_service.dump(db_session)

    # 중간 형태는 문자열이 맞다 — JSON 이니까.
    assert payload["tables"]["opportunities"][0]["deadline"] == when.isoformat()

    db_session.query(models.Opportunity).delete()
    db_session.commit()

    transfer_service.load(db_session, payload)

    restored = db_session.query(models.Opportunity).first()

    assert isinstance(restored.deadline, datetime)
    assert restored.deadline == when


def test_refuses_a_file_from_a_different_schema(db_session):
    payload = transfer_service.dump(db_session)
    payload["schema_revision"] = "0001_something_else"

    with pytest.raises(transfer_service.TransferError) as caught:
        transfer_service.load(db_session, payload)

    assert "리비전" in str(caught.value)


def test_refuses_an_unknown_table(db_session):
    payload = transfer_service.dump(db_session)
    payload["tables"]["나중에생긴것"] = [{"id": 1}]

    with pytest.raises(transfer_service.TransferError):
        transfer_service.load(db_session, payload)


def test_refuses_an_unknown_column(db_session):
    _populate(db_session)

    payload = transfer_service.dump(db_session)
    payload["tables"]["skills"][0]["없는칼럼"] = 1

    with pytest.raises(transfer_service.TransferError) as caught:
        transfer_service.load(db_session, payload)

    assert "없는칼럼" in str(caught.value)


def test_import_endpoint_needs_the_confirm_word(client, db_session):
    _populate(db_session)

    payload = client.get("/transfer/export").json()

    # 확인 문구 없이
    response = client.post("/transfer/import", json=payload)
    assert response.status_code == 422

    # 틀린 확인 문구
    response = client.post(
        "/transfer/import?confirm=yes", json=payload
    )
    assert response.status_code == 400

    # 데이터는 그대로여야 한다.
    assert db_session.query(models.Skill).count() == 2

    response = client.post(
        "/transfer/import?confirm=REPLACE", json=payload
    )
    assert response.status_code == 200
    assert response.json()["written"]["skills"] == 2


def test_export_endpoint_reports_what_it_holds(client, db_session):
    _populate(db_session)

    payload = client.get("/transfer/export").json()

    assert payload["format"] == transfer_service.FORMAT_VERSION
    assert transfer_service.counts(payload)["skills"] == 2
    assert "opportunity_skills" in payload["tables"]


def test_dump_covers_every_table_not_just_the_ones_with_rows(db_session):
    """빈 백업을 성공이라고 말한 적이 있다.

    transfer 가 models 를 임포트하지 않으면 metadata 가 비고,
    내보내기는 조용히 빈 파일을 만든다. 개수가 아니라 테이블
    목록을 본다.
    """
    from app.database import Base

    payload = transfer_service.dump(db_session)

    expected = {table.name for table in Base.metadata.sorted_tables}

    assert len(expected) > 20
    assert set(payload["tables"]) == expected

    # 연결 테이블도 빠지면 안 된다 — 관계가 여기 있다.
    assert "opportunity_skills" in payload["tables"]
    assert "project_skills" in payload["tables"]
    assert "experience_skills" in payload["tables"]


# --------------------------------
# 오래된 파일로 덮어쓰기
#
# 로컬과 배포본은 서로를 모른다. 배포본에서 사흘 동안 일한 뒤
# 그 전에 뜬 로컬 파일을 올리면 그 사흘이 통째로 사라진다.
# --------------------------------

def _work_at(db, when):
    """그 시각에 무언가를 끝냈다는 기록."""
    from datetime import date

    db.add(models.DailyPlanTask(
        plan_date=date.today(), position=0, task_type="project",
        title="배포본에서 한 일", minutes=45, reason="테스트",
        status="done", completed_at=when,
    ))
    db.commit()


def test_it_refuses_a_file_missing_the_work_here(db_session):
    from datetime import datetime

    # 파일은 9월 1일까지의 작업만 담고 있다
    _work_at(db_session, datetime(2026, 9, 1, 10, 0))
    payload = transfer_service.dump(db_session)

    # 그 뒤 서버에서 더 일했다
    _work_at(db_session, datetime(2026, 9, 5, 21, 0))

    with pytest.raises(transfer_service.StaleFile) as caught:
        transfer_service.load(db_session, payload)

    assert "없는 작업" in str(caught.value)

    # 그리고 아무것도 지우지 않았어야 한다
    assert db_session.query(models.DailyPlanTask).count() == 2


def test_a_file_that_contains_the_work_goes_through(db_session):
    from datetime import datetime

    _work_at(db_session, datetime(2026, 9, 5, 21, 0))

    payload = transfer_service.dump(db_session)

    transfer_service.load(db_session, payload)


def test_a_late_export_does_not_excuse_missing_work(db_session):
    """이 구멍으로 한 번 그대로 통과했다.

    배포본에서 14:30 에 한 일이 있는데, 로컬에서 14:40 에 뜬
    파일이라 "최신" 으로 보여 통과했다. exported_at 은 파일을
    언제 떴는지일 뿐, 저쪽 작업을 담고 있는지와 무관하다.
    """
    from datetime import datetime

    payload = transfer_service.dump(db_session)
    payload["exported_at"] = datetime(2026, 9, 10, 14, 40).isoformat()

    _work_at(db_session, datetime(2026, 9, 10, 14, 30))

    with pytest.raises(transfer_service.StaleFile):
        transfer_service.load(db_session, payload)


def test_you_can_still_force_it(db_session):
    from datetime import datetime

    payload = transfer_service.dump(db_session)

    _work_at(db_session, datetime(2026, 9, 5, 21, 0))

    result = transfer_service.load(db_session, payload, allow_stale=True)

    assert result["written"] == {}


def test_an_untouched_server_accepts_anything(db_session):
    """아무도 안 쓴 배포본에는 어떤 파일이든 올릴 수 있다."""
    payload = transfer_service.dump(db_session)

    transfer_service.load(db_session, payload)


def test_the_endpoint_answers_409_not_400(client, db_session):
    """형식 오류(400)와 구분해야 "덮어쓸까요?" 를 물어볼 수 있다."""
    from datetime import datetime

    payload = client.get("/transfer/export").json()

    _work_at(db_session, datetime(2026, 9, 5, 21, 0))

    response = client.post(
        "/transfer/import?confirm=REPLACE", json=payload
    )

    assert response.status_code == 409

    forced = client.post(
        "/transfer/import?confirm=REPLACE&allow_stale=true", json=payload
    )

    assert forced.status_code == 200


def test_server_only_snapshots_survive_an_import(db_session):
    """쌓이기만 하는 기록은 대체하지 않는다.

    로컬 파일에는 스냅샷 6줄, 서버에는 그 뒤로 스케줄러가 쌓은 줄이
    더 있었다. 대체하면서 두 번 사라졌다 (25 → 6, 82 → 6).
    """
    from datetime import datetime

    skill = models.Skill(name="SQL", category="data")
    db_session.add(skill)
    db_session.flush()

    def snap(i, when):
        return models.MarketSnapshot(
            id=i, skill_id=skill.id, opportunity_count=1,
            total_opportunities=2, percentage=50, captured_at=when,
        )

    db_session.add(snap(1, datetime(2026, 9, 2)))
    db_session.commit()

    payload = transfer_service.dump(db_session)   # 로컬: 1줄

    # 그 뒤 서버에서 스케줄러가 쌓았다
    db_session.add_all([snap(2, datetime(2026, 9, 12)), snap(3, datetime(2026, 9, 13))])
    db_session.commit()

    result = transfer_service.load(db_session, payload)

    ids = sorted(r.id for r in db_session.query(models.MarketSnapshot).all())
    assert ids == [1, 2, 3]
    assert result["kept"] == {"market_snapshots": 2}


def test_other_tables_are_still_replaced_not_merged(db_session):
    """보호는 쌓이기만 하는 기록에만. 나머지는 여전히 대체한다."""
    db_session.add(models.Skill(name="Rust", category="lang"))
    db_session.commit()

    empty = transfer_service.dump(db_session)
    empty["tables"]["skills"] = []

    transfer_service.load(db_session, empty, allow_stale=True)

    assert db_session.query(models.Skill).count() == 0
