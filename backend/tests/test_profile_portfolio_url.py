"""프로필의 포트폴리오 주소.

지원서마다 내는 주소를 둘 칸이 없었다. github_url(깃허브 프로필)과
blog_url(블로그)은 다른 것이고, portfolio_entries 는 프로젝트를 담는 표다.
"""


def test_it_starts_empty(client):
    assert client.get("/profile").json()["portfolio_url"] == ""


def test_it_can_be_saved_and_read_back(client):
    body = client.patch("/profile", json={
        "portfolio_url": "https://nocked115.github.io/",
    }).json()

    assert body["portfolio_url"] == "https://nocked115.github.io/"
    assert client.get("/profile").json()["portfolio_url"] == "https://nocked115.github.io/"


def test_saving_it_does_not_wipe_the_other_links(client):
    client.patch("/profile", json={
        "github_url": "https://github.com/nocked115",
        "blog_url": "https://velog.io/@hyunnnsle/posts",
    })

    body = client.patch("/profile", json={"portfolio_url": "https://nocked115.github.io/"}).json()

    assert body["github_url"] == "https://github.com/nocked115"
    assert body["blog_url"] == "https://velog.io/@hyunnnsle/posts"


def test_it_refuses_a_non_web_link(client):
    """화면이 이 값을 href 에 넣는다. javascript: 는 받지 않는다."""
    assert client.patch("/profile", json={
        "portfolio_url": "javascript:alert(1)",
    }).status_code == 422
