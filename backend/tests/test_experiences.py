

def test_the_deeper_fields_round_trip(client):
    """지원서를 쓸 때마다 다시 떠올리던 것들 — 한 번 적으면 남는다."""
    made = client.post("/experiences", json={
        "experience_type": "project",
        "title": "추천시스템 프로젝트",
        "contribution": "모델 구현 전부와 발표 자료",
        "stakeholders": "팀원 3명 · 교수님 · 수업 청중",
        "obstacles": "도메인 갭으로 융합이 단독을 못 넘어 backbone 을 바꿔 실험을 분리",
        "learned": "다시 한다면 해상도부터 맞추고 시작",
        "reusable": "전처리 스크립트와 노트북이 남아 재현 가능",
        "target_roles": "데이터 사이언티스트 · ML 엔지니어",
        "questions": "실패 경험 / 협업 중 갈등 / 문제 해결 과정",
    }).json()

    row = next(e for e in client.get("/experiences").json() if e["id"] == made["id"])

    assert row["contribution"] == "모델 구현 전부와 발표 자료"
    assert "실패 경험" in row["questions"]

    patched = client.patch(f"/experiences/{made['id']}", json={"questions": "리더십"}).json()
    assert patched["questions"] == "리더십"
