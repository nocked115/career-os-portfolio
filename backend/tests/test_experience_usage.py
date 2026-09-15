"""경험이 어디에 쓰였고, 무엇이 비어 있는가.

경험은 한 번 적고 여러 지원서에 꺼내 쓰는 것이다. 어느 지원서에 썼는지
안 보이면 재사용한다는 사실이 안 보이고, 결과가 빈 채로 지원서에 들어간다.
"""


def _experience(client, **fields):
    body = {"experience_type": "project", "title": "이탈 예측", **fields}
    return client.post("/experiences", json=body).json()


def _usage(client):
    response = client.get("/experiences/usage")
    assert response.status_code == 200
    return {row["experience_id"]: row for row in response.json()}


def test_usage_lists_the_applications_that_matched_an_experience(client):
    experience = _experience(client)

    posting = client.post(
        "/opportunities",
        json={
            "opportunity_type": "job",
            "title": "데이터 분석가",
            "organization": "어떤회사",
            "source": "manual",
        },
    ).json()
    application = client.post(
        "/applications", json={"opportunity_id": posting["id"]}
    ).json()

    client.put(
        f"/applications/{application['id']}/experiences/{experience['id']}",
        json={
            "application_id": application["id"],
            "experience_id": experience["id"],
            "match_score": 80,
            "match_notes": "",
        },
    )

    used = _usage(client)[experience["id"]]["applications"]

    assert [(row["title"], row["organization"]) for row in used] == [
        ("데이터 분석가", "어떤회사")
    ]


def test_usage_names_the_empty_fields_in_korean(client):
    experience = _experience(client, problem="이탈이 늘었다")

    missing = _usage(client)[experience["id"]]["missing"]

    assert "결과" in missing
    assert "상황과 과제" not in missing


def test_suggestions_point_at_the_next_evidence_step(client):
    project = client.post(
        "/projects",
        json={"name": "배포 파이프라인", "status": "completed", "progress_percent": 100},
    ).json()

    body = client.get(f"/projects/{project['id']}/evidence").json()

    assert body["next_action"]["key"] == "record_results"
    labels = " ".join(action["label"] for action in body["actions"])
    assert "Experience" not in labels
    assert "Portfolio" not in labels


def test_resume_bullet_names_missing_parts_in_korean(client):
    experience = _experience(client, actions="모델 학습")
    entry = client.post(f"/experiences/{experience['id']}/portfolio-entry").json()

    body = client.post(f"/portfolio-entries/{entry['id']}/resume-bullet").json()

    assert "결과" in body["missing_labels"]
    assert "results" not in (body["message"] or "")


def test_the_evidence_breakdown_speaks_korean(client):
    labels = [item["label"] for item in client.get("/analytics/evidence").json()["breakdown"]]

    assert "경험" in labels
    assert "Experience" not in labels
