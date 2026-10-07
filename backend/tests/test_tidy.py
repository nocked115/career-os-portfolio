"""쌓인 공고 치우기 — 중복 묶기와 마감 내리기.

수현: "중복 공고 일주일 단위로 좀 치워주면 안 되나, 원문에 들어갔을 때
마감 처리 또는 못 들어가면 그냥 마감해버리고."
"""

from datetime import date, datetime, timedelta

from app import models
from app.services import tidy


TODAY = date(2026, 10, 6)


def _posting(db, title, org="SK인텔릭스", source="work24",
             description="", skills=(), deadline=None, status="discovered"):
    row = models.Opportunity(
        opportunity_type="job", title=title, organization=org,
        source=source, description=description, deadline=deadline, status=status,
    )
    row.skills.extend(skills)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_the_same_posting_written_four_ways_is_one_group(db_session):
    """실제로 났던 것 — 수집원이 다섯이라 같은 공고가 네 줄이었다."""
    keep = _posting(db_session, "SK인텔릭스｜데이터 분석 인턴 채용",
                    source="manual", description="x" * 1000)
    _posting(db_session, "[SK인텔릭스] 데이터 분석 인턴 채용", source="linkareer")
    _posting(db_session, "데이터 분석 인턴")
    _posting(db_session, "데이터 분석 인턴 채용")

    groups = tidy.find_duplicates(db_session)

    assert len(groups) == 1
    assert groups[0]["keep"]["id"] == keep.id
    assert len(groups[0]["drop"]) == 3


def test_a_posting_with_an_application_is_never_dropped(db_session):
    """치우면 그 지원서가 어느 공고인지 화면에서 사라진다. 실제로 깨뜨렸다."""
    _posting(db_session, "데이터 분석 인턴 채용", source="manual", description="x" * 900)
    attached = _posting(db_session, "데이터 분석 인턴")

    db_session.add(models.Application(opportunity_id=attached.id, status="interested"))
    db_session.commit()

    groups = tidy.find_duplicates(db_session)

    assert groups == [] or attached.id not in [
        row["id"] for item in groups for row in item["drop"]
    ]


def test_the_richest_row_is_kept(db_session):
    """설명이 길고 스킬이 붙은 것이 원본에 가깝다."""
    skill = models.Skill(name="SQL", category="data", level=0)
    db_session.add(skill)
    db_session.commit()

    thin = _posting(db_session, "데이터 분석 인턴")
    rich = _posting(db_session, "데이터 분석 인턴 채용",
                    description="x" * 500, skills=[skill])

    group = tidy.find_duplicates(db_session)[0]

    assert group["keep"]["id"] == rich.id
    assert [row["id"] for row in group["drop"]] == [thin.id]


def test_different_companies_are_not_merged(db_session):
    _posting(db_session, "데이터 분석 인턴", org="SK인텔릭스")
    _posting(db_session, "데이터 분석 인턴", org="네이버")

    assert tidy.find_duplicates(db_session) == []


def test_an_expired_posting_is_closed(db_session):
    old = _posting(db_session, "지난 공고",
                   deadline=datetime(2026, 9, 30), status="interested")
    _posting(db_session, "열린 공고", deadline=datetime(2026, 12, 31))

    expired = tidy.find_expired(db_session, TODAY)

    assert [row["id"] for row in expired] == [old.id]
    assert expired[0]["days_past"] == 6


def test_a_posting_without_a_deadline_is_left_alone(db_session):
    """상시채용을 마감으로 내리면 안 된다. 모르는 것은 모르는 대로 둔다."""
    _posting(db_session, "상시 채용", deadline=None)

    assert tidy.find_expired(db_session, TODAY) == []


def test_applying_changes_status_but_does_not_delete(db_session):
    """되돌릴 수 있어야 한다."""
    _posting(db_session, "데이터 분석 인턴 채용", source="manual", description="x" * 900)
    dropped = _posting(db_session, "데이터 분석 인턴")
    expired = _posting(db_session, "지난 공고", org="다른회사",
                       deadline=datetime(2026, 9, 1))

    result = tidy.apply(db_session, TODAY)

    db_session.expire_all()
    assert result["will_archive"] == 1
    assert result["will_close"] == 1
    assert dropped.status == "archived"
    assert expired.status == "closed"
    assert db_session.get(models.Opportunity, dropped.id) is not None


def test_preview_does_not_change_anything(db_session):
    _posting(db_session, "데이터 분석 인턴 채용", source="manual", description="x" * 900)
    row = _posting(db_session, "데이터 분석 인턴")

    tidy.preview(db_session, TODAY)

    db_session.expire_all()
    assert row.status == "discovered"


# --------------------------------
# 서울 밖 채용 행사
# --------------------------------

def _event(db, title, location="", status="discovered"):
    row = models.Opportunity(
        opportunity_type="job_event", title=title, location=location,
        organization="", source="work24_event", status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_a_fair_outside_seoul_is_archived(db_session):
    """박람회는 그날 그 자리에 가야 하는 것이라 못 가면 끝이다."""
    _event(db_session, "2026 수원시 일자리 박람회", "수원컨벤션센터")
    _event(db_session, "2026 광진구 일자리박람회", "광진구청 5층 대강당")

    far = tidy.find_far_events(db_session)

    assert [row["title"] for row in far] == ["2026 수원시 일자리 박람회"]


def test_seoul_is_recognised_by_district_name(db_session):
    for title in ("2026동대문구 온.오프 취업박람회", "영등포구 2026 천하제일 JOB 취업박람회"):
        _event(db_session, title)

    assert tidy.find_far_events(db_session) == []


def test_an_event_without_a_place_is_archived(db_session):
    """못 가는 행사를 남기는 비용이, 갈 수 있는 것 하나 놓치는 비용보다 작다."""
    _event(db_session, "채용박람회")

    assert len(tidy.find_far_events(db_session)) == 1


def test_a_job_posting_is_never_touched(db_session):
    """공고는 지역이 멀어도 지원할 수 있다 — 원격 · 이사 · 지사 배치."""
    _posting(db_session, "데이터 분석", org="부산회사")

    assert tidy.find_far_events(db_session) == []


def test_applying_archives_and_says_why(db_session):
    event = _event(db_session, "2026 부천 잡페스타", "부천고용복지플러스센터")

    tidy.apply(db_session, TODAY)

    db_session.expire_all()
    assert event.status == "archived"
    assert event.blocked_reason == tidy.FAR_REASON


def test_tidying_clears_favorites_on_what_it_puts_away(db_session):
    """보관함에 있는 공고가 즐겨찾기로 계속 떠 있었다 — 실제로 그랬다."""
    _posting(db_session, "데이터 분석 인턴 채용", source="manual", description="x" * 900)
    dropped = _posting(db_session, "데이터 분석 인턴")
    dropped.favorite = True

    expired = _posting(db_session, "지난 공고", org="다른회사",
                       deadline=datetime(2026, 9, 1))
    expired.favorite = True

    event = _event(db_session, "2026 수원시 일자리 박람회", "수원컨벤션센터")
    event.favorite = True
    db_session.commit()

    tidy.apply(db_session, TODAY)

    db_session.expire_all()
    assert dropped.favorite is False
    assert expired.favorite is False
    assert event.favorite is False


def test_collecting_tidies_right_after_instead_of_waiting_for_a_person(client, db_session):
    """수현: "수집 직후 자동으로 치우도록."

    사람이 tidy 를 누르기 전까지 서울 밖 박람회와 지난 공고가 기회 목록
    맨 위에 쌓여 있었다. 치우는 일이 사람 몫으로 남아 있으면 안 치운다.
    """
    stale = _posting(
        db_session, "2024 데이터 직무 박람회", org="부산테크노파크",
        source="work24", deadline=date.today() - timedelta(days=30),
    )

    body = client.post("/automation/run").json()

    assert "tidied" in body
    assert body["tidied"]["closed"] >= 1

    db_session.expire_all()
    assert stale.status == "closed"


def test_tidying_happens_before_the_demand_is_counted(client, db_session):
    """순서가 뒤집히면 이미 지난 공고가 그 주의 수요로 잡힌다.

    "지원할 수 없는 공고는 지금의 수요가 아니다" 는 규칙이 수집 때도
    지켜지려면, 치우는 일이 수요 집계보다 먼저여야 한다.
    """
    from app.services import market

    stale = _posting(
        db_session, "지난 공고", deadline=date.today() - timedelta(days=10)
    )

    client.post("/automation/run")

    db_session.expire_all()
    assert stale.status == "closed"
    assert stale.id not in {row.id for row in market.demand_opportunities(db_session)}


def test_what_is_inside_the_parentheses_can_be_the_whole_difference(db_session):
    """실제로 깨뜨렸다 — 카카오 Pre-training 이 Post-training 의 중복으로
    보관됐다. 괄호 안을 통째로 지우니 둘의 제목이 같아져서다.

    괄호 안이 군더더기일 때도 있지만("(신입/경력)"), 직무 그 자체일 때도
    있다. 통째로 지우는 건 **다른 공고를 같다고 하는** 쪽으로 틀리고,
    그게 이 모듈이 가장 피해야 하는 실수다.
    """
    pre = _posting(db_session, "LLM Research Engineer (Pre-training) (신입/경력)",
                   org="카카오", source="kakao")
    post = _posting(db_session, "LLM Research Engineer (Post-training) (신입/경력)",
                    org="카카오", source="kakao")

    assert tidy.find_duplicates(db_session) == []

    tidy.apply(db_session)
    db_session.expire_all()
    assert pre.status == "discovered"
    assert post.status == "discovered"


def test_the_same_role_written_with_and_without_the_noise_still_groups(db_session):
    """군더더기만 다른 것은 여전히 하나로 묶인다."""
    _posting(db_session, "데이터 엔지니어 채용 (신입/경력)", org="카카오", source="manual",
             description="x" * 500)
    _posting(db_session, "데이터 엔지니어 모집공고", org="카카오", source="linkareer")

    groups = tidy.find_duplicates(db_session)

    assert len(groups) == 1
    assert len(groups[0]["drop"]) == 1


def test_the_tidy_says_why_it_put_a_posting_away(db_session):
    """수현: "석박사 요건 때문에 마감으로 판단한 건지, 나랑 안 맞아서 버린
    건지 판단하는 거 만들었는지."

    사람이 정한 것에는 까닭이 있었는데 **앱이 치운 것에는 없었다.**
    그래서 잘못 묶인 카카오 공고 하나를 한참 못 봤다.
    """
    keep = _posting(db_session, "데이터 엔지니어", source="manual",
                    description="x" * 500)
    drop = _posting(db_session, "데이터 엔지니어 채용", source="linkareer")
    gone = _posting(db_session, "지난 공고",
                    deadline=date.today() - timedelta(days=3))

    tidy.apply(db_session)
    db_session.expire_all()

    # 그냥 "중복" 이 아니라 **어느 줄로 묶였는지** 적는다. 잘못 묶였을 때
    # 그게 보여야 알아본다.
    assert drop.tidied_reason == "'데이터 엔지니어' 과 같은 공고로 묶음"
    assert "마감 지남" in gone.tidied_reason
    assert keep.tidied_reason == ""


def test_an_archived_posting_actually_lands_in_the_archive(db_session):
    """상태만 바꾸고 칸을 안 주면 검토 목록에 그대로 남는다 —
    마감이 없는 공고가 실제로 그랬다."""
    from app.services import opportunity as opportunity_service

    _posting(db_session, "데이터 엔지니어", source="manual", description="x" * 500)
    drop = _posting(db_session, "데이터 엔지니어 채용", source="linkareer")

    tidy.apply(db_session)
    db_session.expire_all()

    match = opportunity_service.build_match(db_session, drop, priority_entries=[])

    assert match["lane"] == "archived"
    assert match["archive_reason"] == "'데이터 엔지니어' 과 같은 공고로 묶음"
