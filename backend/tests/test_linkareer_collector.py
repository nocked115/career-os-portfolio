"""링커리어 인턴 목록 — 신입에게 가장 부족한 인턴을 메우는 자리.

약관 제16조가 막는 것은 "서버에 부하를 일으켜 정상 서비스를 방해하는" 자동 접속이다.
그래서 하루 한 번 · 목록 세 쪽 · 공고 상세는 열지 않는 선을 코드로 박았다.
"""

import json

import pytest

from app.collectors import base, linkareer


def _page(*activities):
    data = {"props": {"apolloState": {
        f"Activity:{item['id']}": {"__typename": "Activity", **item} for item in activities
    }}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


PAGES = {
    "https://linkareer.com/robots.txt": "User-agent: *\nAllow: /\nDisallow: /stem/learn/\n",
    "https://linkareer.com/list/intern": _page(
        {"id": "1", "title": "화수분AI 프로덕트 엔지니어 인턴 채용",
         "organizationName": "화수분에이아이", "recruitCloseAt": "1797519599999"},
        {"id": "2", "title": "[인턴 모집] 콘텐츠 마케팅 매니저를 찾습니다!",
         "organizationName": "어느 회사", "recruitCloseAt": None},
    ),
    "https://linkareer.com/list/intern?page=2": _page(
        {"id": "3", "title": "데이터 분석가 (경력 5년 이상)", "organizationName": "경력만"},
    ),
    "https://linkareer.com/list/intern?page=3": _page(),
}


def _opener(url):
    if url not in PAGES:
        raise AssertionError(f"목록 밖을 열었다: {url}")
    return PAGES[url]


def test_only_data_and_ai_interns_are_kept():
    kept = linkareer.fetch(_opener)

    # 마케팅 인턴과 경력 전용은 뺀다.
    # ("인턴" 과 "(경력)" 이 함께 있으면 신입도 받는 자리로 본다 — 신입 표시가 이긴다.)
    assert [job["id"] for job in kept] == ["1"]
    assert kept[0]["company"] == "화수분에이아이"


def test_detail_pages_are_never_opened():
    """공고마다 따로 열면 부하가 된다. 목록에 이미 제목 · 회사 · 마감이 있다."""
    linkareer.fetch(_opener)  # _opener 가 목록 밖 주소에서 실패한다


def test_robots_blocking_us_stops_collection():
    blocked = dict(PAGES, **{
        "https://linkareer.com/robots.txt": "User-agent: *\nDisallow: /\n",
    })

    with pytest.raises(base.CollectorError) as caught:
        linkareer.fetch(lambda url: blocked[url])

    assert "robots" in str(caught.value)


def test_a_changed_page_is_reported_not_swallowed():
    with pytest.raises(base.CollectorError) as caught:
        linkareer.fetch(lambda url: "<html>바뀐 화면</html>" if "robots" not in url else "")

    assert "구조가 바뀐" in str(caught.value)


def test_fields_land_where_they_belong():
    normalized = linkareer.normalize(linkareer.fetch(_opener)[0])

    assert normalized["source"] == "linkareer"
    assert normalized["source_url"] == "https://linkareer.com/activity/1"
    assert normalized["employment_type"] == "인턴"
    assert normalized["deadline"] is not None
    assert "주소로 가져오기" in normalized["description"]
