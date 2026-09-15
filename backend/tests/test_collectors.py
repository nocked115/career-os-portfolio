"""Mission 023 - 수집원 어댑터 계약."""

from datetime import datetime

import pytest

from app import collectors
from app.collectors import base


# --------------------------------
# 정규화 계약
# --------------------------------

def test_source_and_title_are_required():
    with pytest.raises(base.CollectorError):
        base.normalize_opportunity(source="", external_id=1, title="X")

    with pytest.raises(base.CollectorError):
        base.normalize_opportunity(source="s", external_id=1, title="")


def test_unknown_opportunity_type_is_rejected():
    with pytest.raises(base.CollectorError):
        base.normalize_opportunity(
            source="s",
            external_id=1,
            title="X",
            opportunity_type="hackathon",
        )


def test_missing_fields_stay_empty_rather_than_guessed():
    result = base.normalize_opportunity(
        source="s",
        external_id=None,
        title="X",
    )

    assert result["organization"] == ""
    assert result["role"] == ""
    assert result["location"] == ""
    assert result["deadline"] is None
    assert result["source_external_id"] is None


def test_deadline_parsing_accepts_common_formats():
    expected = datetime(2026, 9, 30)

    for value in ("2026-09-30", "2026/09/30", "2026.09.30"):
        assert base.parse_deadline(value) == expected


def test_unparseable_deadline_becomes_none():
    """해석할 수 없으면 날짜를 만들어내지 않는다."""
    for value in ("상시채용", "ASAP", "", None, "next month"):
        assert base.parse_deadline(value) is None


def test_external_id_is_stringified():
    result = base.normalize_opportunity(
        source="s", external_id=42, title="X"
    )

    assert result["source_external_id"] == "42"


# --------------------------------
# 레지스트리
# --------------------------------

def test_registry_exposes_available_collectors():
    names = [c.SOURCE_NAME for c in collectors.available_collectors()]

    assert "mock" in names


def test_get_collector_returns_none_for_unknown():
    assert collectors.get_collector("does-not-exist") is None


def test_every_registered_collector_satisfies_the_contract():
    """새 수집원을 추가해도 계약을 지키는지 여기서 걸린다."""
    for name, collector in collectors.REGISTRY.items():
        assert collector.SOURCE_NAME == name

        assert callable(collector.is_available)
        assert callable(collector.fetch)
        assert callable(collector.normalize)

        # 켜진 수집원만 실제로 부른다. 사람인처럼 키가 필요한 수집원을
        # 무조건 부르면 테스트가 외부 API 로 요청을 보낸다.
        if not collector.is_available():
            continue

        for raw in collector.fetch():
            normalized = collector.normalize(raw)

            assert normalized["source"] == name
            assert normalized["title"]
            assert normalized["opportunity_type"] in base.OPPORTUNITY_TYPES


def test_mock_produces_both_a_job_and_a_competition():
    types = {
        collectors.mock.normalize(raw)["opportunity_type"]
        for raw in collectors.mock.fetch()
    }

    assert types == {"job", "competition"}
