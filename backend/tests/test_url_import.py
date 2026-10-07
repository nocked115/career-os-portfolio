"""공고 주소로 가져오기 — 사람이 고른 한 건만, robots 가 막으면 멈춘다."""

import pytest

from app.services import url_import


PAGE = """<html><head><title>x</title><style>a{}</style></head><body>
<h1>데이터 사이언티스트 (신입)</h1>
<p>테스트컴퍼니</p>
<p>지원 자격: 학사 이상, Python · SQL 활용 가능자</p>
<p>모집 마감: 2026-10-02</p>
<script>track()</script>
<p>근무지: 서울 강남구. 자세한 내용은 채용 페이지를 참고하세요. 전형은 서류와 면접으로 진행합니다.</p>
</body></html>"""


def _opener(pages):
    def open_url(url):
        if url not in pages:
            raise url_import.ImportError_("없음")
        return pages[url]
    return open_url


def test_a_page_becomes_text_without_scripts():
    text = url_import.to_text(PAGE)

    assert "데이터 사이언티스트 (신입)" in text
    assert "track()" not in text and "<p>" not in text


def test_robots_blocking_us_stops_the_fetch():
    pages = {
        "https://jobs.example.com/robots.txt": "User-agent: *\nDisallow: /\n",
        "https://jobs.example.com/1": PAGE,
    }

    with pytest.raises(url_import.ImportError_) as caught:
        url_import.fetch_posting("https://jobs.example.com/1", _opener(pages))

    assert "복사해" in str(caught.value)


def test_robots_allowing_us_lets_it_through():
    pages = {
        "https://jobs.example.com/robots.txt": "User-agent: *\nDisallow: /admin\n",
        "https://jobs.example.com/1": PAGE,
    }

    text = url_import.fetch_posting("https://jobs.example.com/1", _opener(pages))

    assert "테스트컴퍼니" in text


def test_a_missing_robots_file_is_not_a_block():
    pages = {"https://jobs.example.com/1": PAGE}

    assert url_import.fetch_posting("https://jobs.example.com/1", _opener(pages))


@pytest.mark.parametrize("url", [
    "http://localhost:8130/x",
    "http://127.0.0.1/x",
    "file:///etc/passwd",
    "ftp://example.com/x",
])
def test_internal_and_odd_addresses_are_refused(url):
    with pytest.raises(url_import.ImportError_):
        url_import.fetch_posting(url, _opener({}))


def test_a_page_with_almost_no_text_falls_back_to_pasting():
    pages = {"https://jobs.example.com/1": "<html><body><div id='root'></div></body></html>"}

    with pytest.raises(url_import.ImportError_) as caught:
        url_import.fetch_posting("https://jobs.example.com/1", _opener(pages))

    assert "붙여넣어" in str(caught.value)


def test_the_endpoint_answers_422_with_the_reason(client):
    refused = client.post("/opportunities/fetch-url", json={"url": "http://127.0.0.1/x"})

    assert refused.status_code == 422


def test_the_site_name_is_stripped_from_the_title():
    html = "<html><head><title>[오성푸드] 경리 사무원 모집 - 사람인</title></head><body>" + (
        "<p>지원 자격: 학사 이상이며 관련 경험이 있는 분을 찾습니다. 근무지는 서울입니다.</p>" * 2
    ) + "</body></html>"
    pages = {"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=1": html}

    text = url_import.fetch_posting(
        "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=1", _opener(pages)
    )

    assert text.splitlines()[0] == "[오성푸드] 경리 사무원 모집"


def test_repeated_navigation_lines_are_dropped_once():
    text = url_import.to_text(
        "<div>공채는 역시, 사람인</div><div>공채는 역시, 사람인</div><div>본문 내용</div>"
    )

    assert text.count("공채는 역시, 사람인") == 1
