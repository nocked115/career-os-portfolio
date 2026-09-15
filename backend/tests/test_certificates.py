"""자격증 · 어학.

번호는 담지 않는다. 만료는 미리 말한다. 공고의 자격 경고 옆에 내가 가진
것을 나란히 보여주되, 충족 여부는 판단하지 않는다.
"""

from datetime import date

from app import models
from app.services import certificates as service


def _add(client, **fields):
    body = {"category": "language", "name": "TOEIC", **fields}
    return client.post("/certificates", json=body)


def test_certificates_are_grouped_by_language_and_job(client):
    _add(client, name="TOEIC", score="900", detail="LC 450 · RC 450",
         acquired_on="2026-07-26", expires_on="2028-07-26")
    _add(client, category="job", name="빅데이터분석기사", acquired_on="2026-07-10")

    body = client.get("/certificates").json()

    assert [item["name"] for item in body["language"]] == ["TOEIC"]
    assert [item["name"] for item in body["job"]] == ["빅데이터분석기사"]
    assert body["job"][0]["expiry_state"] == "none"
    assert body["summary"]["held"] == 2


def test_expiry_is_warned_ahead():
    today = date(2026, 9, 15)
    certificate = models.Certificate(category="job", name="SQLD", status="held")

    certificate.expires_on = date(2027, 1, 1)
    assert service.serialize(certificate, today)["expiry_state"] == "soon"

    certificate.expires_on = date(2026, 9, 1)
    assert service.serialize(certificate, today)["expiry_state"] == "expired"

    certificate.expires_on = date(2028, 1, 1)
    assert service.serialize(certificate, today)["expiry_state"] == "ok"


def test_expiry_before_acquisition_is_rejected(client):
    assert _add(client, acquired_on="2026-07-26", expires_on="2026-01-01").status_code == 422

    created = _add(client, acquired_on="2026-07-26").json()
    response = client.patch(f"/certificates/{created['id']}", json={"expires_on": "2026-01-01"})
    assert response.status_code == 422


def test_an_unknown_category_is_rejected(client):
    assert _add(client, category="hobby").status_code == 422


def test_certificate_numbers_are_not_kept(client):
    """자격번호를 보내도 저장하지 않는다. 담을 칸이 없다."""
    created = _add(client, number="BAE-000000").json()

    assert "number" not in created
    assert "BAE-000000" not in str(client.get("/certificates").json())


def test_certificates_can_be_edited_and_removed(client):
    created = _add(client, score="900").json()

    updated = client.patch(f"/certificates/{created['id']}", json={"score": "900"}).json()
    assert updated["score"] == "900"

    client.delete(f"/certificates/{created['id']}")
    assert client.get("/certificates").json()["language"] == []


def test_a_language_flag_shows_what_i_hold(client):
    _add(client, name="OPIc", score="IH")
    _add(client, name="토익스피킹", status="planned")

    client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "AI 직무",
            "source": "manual",
            "description": "지원자격\n영어회화 최소등급: IM(OPIc)\n",
        },
    )

    match = client.get("/opportunities/matches").json()["matches"][0]
    groups = {group["flag_kind"]: group for group in match["my_certificates"]}

    # 준비 중인 것은 "가진 것" 이 아니다.
    assert [item["name"] for item in groups["language"]["certificates"]] == ["OPIc"]


def test_the_paste_preview_shows_them_too(client):
    _add(client, name="OPIc", score="IH")

    body = client.post(
        "/opportunities/parse", json={"text": "지원자격\nOPIc IM 이상\n", "url": ""}
    ).json()

    assert body["my_certificates"][0]["certificates"][0]["name"] == "OPIc"
