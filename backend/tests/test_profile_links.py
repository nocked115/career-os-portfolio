"""내 GitHub · 블로그 링크와 경험별 글 링크."""


def test_links_can_be_saved_and_read(client):
    body = client.patch("/profile", json={
        "github_url": "https://github.com/example",
        "blog_url": "https://velog.io/@hyunnnsle/posts",
    }).json()

    assert body["github_url"] == "https://github.com/example"
    assert body["blog_url"] == "https://velog.io/@hyunnnsle/posts"


def test_sending_only_links_keeps_the_name(client):
    """name 만 받던 시절이면 링크만 보냈을 때 이름이 지워졌다."""
    client.patch("/profile", json={"name": "Hyun"})
    client.patch("/profile", json={"github_url": "https://github.com/x"})

    assert client.get("/profile").json()["name"] == "Hyun"


def test_sending_only_the_name_keeps_the_links(client):
    client.patch("/profile", json={"blog_url": "https://velog.io/@x"})
    client.patch("/profile", json={"name": "Hyun"})

    assert client.get("/profile").json()["blog_url"] == "https://velog.io/@x"


def test_non_web_links_are_refused(client):
    """화면이 이 값을 href 에 넣는다."""
    response = client.patch("/profile", json={"github_url": "javascript:alert(1)"})

    assert response.status_code == 422


def test_links_can_be_cleared(client):
    client.patch("/profile", json={"blog_url": "https://velog.io/@x"})
    client.patch("/profile", json={"blog_url": ""})

    assert client.get("/profile").json()["blog_url"] == ""


def test_experience_carries_a_blog_link(client):
    body = client.post("/experiences", json={
        "experience_type": "project", "title": "낚시성 기사 탐지",
        "blog_url": "https://velog.io/@hyunnnsle/clickbait",
    }).json()

    assert body["blog_url"] == "https://velog.io/@hyunnnsle/clickbait"
