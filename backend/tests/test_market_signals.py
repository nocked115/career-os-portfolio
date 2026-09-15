"""Mission 023 - 시장 신호와 추세.

통계는 저장된 실제 데이터에서만 계산한다.
비교할 과거가 없으면 추세를 그리지 않는다.
"""

from app import models
from app.services import market as market_service


def _skill(db_session, name, level=0):
    skill = models.Skill(name=name, category="data", level=level)
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(skill)
    return skill


def _opportunity(db_session, title, skills=()):
    opportunity = models.Opportunity(
        opportunity_type="job",
        title=title,
        source="test",
    )
    opportunity.skills.extend(skills)
    db_session.add(opportunity)
    db_session.commit()
    return opportunity


# --------------------------------
# 현재 수요
# --------------------------------

def test_no_opportunities_means_zero_percent(db_session):
    _skill(db_session, "AWS")

    signals = market_service.build_signals(db_session)

    assert signals[0]["opportunity_count"] == 0
    assert signals[0]["percentage"] == 0


def test_percentage_is_computed_from_stored_opportunities(db_session):
    aws = _skill(db_session, "AWS")
    sql = _skill(db_session, "SQL")

    _opportunity(db_session, "A", [aws, sql])
    _opportunity(db_session, "B", [aws])
    _opportunity(db_session, "C", [])
    _opportunity(db_session, "D", [])

    signals = {s["skill"]: s for s in market_service.build_signals(db_session)}

    assert signals["AWS"]["opportunity_count"] == 2
    assert signals["AWS"]["percentage"] == 50
    assert signals["SQL"]["percentage"] == 25


def test_signals_are_sorted_by_demand(db_session):
    low = _skill(db_session, "Low")
    high = _skill(db_session, "High")

    _opportunity(db_session, "A", [high, low])
    _opportunity(db_session, "B", [high])

    signals = market_service.build_signals(db_session)

    assert [s["skill"] for s in signals] == ["High", "Low"]


# --------------------------------
# 스냅샷
# --------------------------------

def test_snapshot_writes_one_row_per_skill(db_session):
    aws = _skill(db_session, "AWS")
    _skill(db_session, "SQL")
    _opportunity(db_session, "A", [aws])

    assert market_service.capture_snapshot(db_session) == 2
    assert db_session.query(models.MarketSnapshot).count() == 2


def test_no_snapshot_when_there_are_no_opportunities(db_session):
    """기회가 없으면 남길 신호가 없다."""
    _skill(db_session, "AWS")

    assert market_service.capture_snapshot(db_session) == 0
    assert db_session.query(models.MarketSnapshot).count() == 0


# --------------------------------
# 추세
# --------------------------------

def test_trend_is_unknown_with_a_single_snapshot(db_session):
    """비교할 과거가 없는데 화살표를 그리지 않는다."""
    aws = _skill(db_session, "AWS")
    _opportunity(db_session, "A", [aws])

    market_service.capture_snapshot(db_session)

    result = market_service.build_signals_with_trend(db_session)
    signal = result["signals"][0]

    assert signal["trend"] == "unknown"
    assert signal["previous_percentage"] is None
    assert result["has_trend_data"] is False


def test_trend_is_unknown_without_any_snapshot(db_session):
    aws = _skill(db_session, "AWS")
    _opportunity(db_session, "A", [aws])

    result = market_service.build_signals_with_trend(db_session)

    assert result["signals"][0]["trend"] == "unknown"
    assert result["snapshot_count"] == 0


def test_rising_demand_is_detected(db_session):
    aws = _skill(db_session, "AWS")
    other = _skill(db_session, "Other")

    # 1회차: 기회 2건 중 AWS 1건 = 50%
    _opportunity(db_session, "A", [aws])
    _opportunity(db_session, "B", [other])
    market_service.capture_snapshot(db_session)

    # 2회차: 기회 3건 중 AWS 3건 = 100%
    _opportunity(db_session, "C", [aws])

    existing = (
        db_session.query(models.Opportunity)
        .filter(models.Opportunity.title == "B")
        .first()
    )
    existing.skills.append(aws)
    db_session.commit()
    market_service.capture_snapshot(db_session)

    signals = {
        s["skill"]: s
        for s in market_service.build_signals_with_trend(db_session)["signals"]
    }

    assert signals["AWS"]["trend"] == "up"
    assert signals["AWS"]["previous_percentage"] == 50
    assert signals["AWS"]["snapshot_percentage"] == 100
    assert signals["AWS"]["change_points"] == 50


def test_falling_demand_is_detected(db_session):
    aws = _skill(db_session, "AWS")

    _opportunity(db_session, "A", [aws])
    market_service.capture_snapshot(db_session)

    for title in ("B", "C", "D"):
        _opportunity(db_session, title, [])
    market_service.capture_snapshot(db_session)

    signal = market_service.build_signals_with_trend(
        db_session
    )["signals"][0]

    assert signal["trend"] == "down"
    assert signal["change_points"] == 25 - 100


def test_small_changes_are_flat(db_session):
    """공고 몇 건 차이로 화살표가 요동치면 안 된다."""
    assert market_service._trend(51, 50) == ("flat", 1)
    assert market_service._trend(48, 50) == ("flat", -2)
    assert market_service._trend(55, 50)[0] == "up"


def test_snapshots_in_the_same_second_still_compare(db_session):
    """SQLite 의 초 단위 타임스탬프에 기대지 않는다."""
    aws = _skill(db_session, "AWS")
    _opportunity(db_session, "A", [aws])
    market_service.capture_snapshot(db_session)
    market_service.capture_snapshot(db_session)

    rows = market_service.recent_snapshots(db_session, aws.id, limit=2)

    assert len(rows) == 2
    assert rows[0].id > rows[1].id


# --------------------------------
# API
# --------------------------------

def test_market_signals_endpoint(client):
    client.post("/skills", json={"name": "Python", "category": "lang"})
    client.post("/opportunities/collect")
    client.post("/analytics/market-snapshots")

    body = client.get("/analytics/market-signals").json()

    assert body["total_opportunities"] == 2
    assert body["source_count"] == 1
    assert body["snapshot_count"] >= 1

    signal = body["signals"][0]
    assert signal["skill"] == "Python"
    assert signal["trend"] in ("up", "down", "flat", "unknown")


def test_market_signals_limit(client):
    for name in ("A", "B", "C"):
        client.post("/skills", json={"name": name, "category": "x"})

    body = client.get("/analytics/market-signals?limit=2").json()

    assert len(body["signals"]) == 2


def test_snapshot_endpoint_reports_what_it_saved(client):
    client.post("/skills", json={"name": "Python", "category": "lang"})
    client.post("/opportunities/collect")

    body = client.post("/analytics/market-snapshots").json()

    assert body["captured_rows"] == 1
    assert body["total_opportunities"] == 2
