"""자격증 · 어학 — 프로필에 붙는 증빙.

번호(자격번호 · 수험번호 · 등록번호)는 담지 않는다. 지원서에 낼 때는 원본
증빙 파일을 쓴다. 앱이 이걸 가진 이유는 두 가지다.

  - 공고의 자격 요건 경고 옆에 "내가 가진 것" 을 보여주기
  - 만료가 다가오는 것을 미리 말하기 (SQLD · TOEFL 처럼 기한이 있는 것)

**충족 여부는 판단하지 않는다.** 공고마다 인정하는 시험과 기준이 다르다
(어떤 회사는 영어회화로 OPIc · 토익스피킹만 인정하는 식). 나란히 보여줄 뿐이다.
"""

from datetime import date

from .. import models


CATEGORY_LABELS = {"language": "어학", "job": "직무 자격"}
STATUS_LABELS = {"held": "보유", "planned": "준비 중"}

# 이 안으로 들어오면 "만료 임박" 이라고 말한다. 반년이면 다시 응시할 시간이 있다.
EXPIRY_SOON_DAYS = 180

# 공고 경고 종류 → 보여줄 자격 구분 (posting_parser.FLAGS 의 kind).
FLAG_CATEGORIES = {"language": "language", "license": "job"}


def serialize(certificate, today: date | None = None) -> dict:
    today = today or date.today()

    if certificate.expires_on is None:
        days, state = None, "none"
    else:
        days = (certificate.expires_on - today).days
        if days < 0:
            state = "expired"
        elif days <= EXPIRY_SOON_DAYS:
            state = "soon"
        else:
            state = "ok"

    return {
        "id": certificate.id,
        "category": certificate.category,
        "category_label": CATEGORY_LABELS.get(certificate.category, "자격"),
        "name": certificate.name,
        "score": certificate.score,
        "detail": certificate.detail,
        "issuer": certificate.issuer,
        "status": certificate.status,
        "status_label": STATUS_LABELS.get(certificate.status, "보유"),
        "acquired_on": certificate.acquired_on,
        "expires_on": certificate.expires_on,
        "note": certificate.note,
        "days_to_expiry": days,
        "expiry_state": state,
    }


def _ordered(db):
    """보유한 것 먼저, 그 안에서 최근에 취득한 순."""
    return sorted(
        db.query(models.Certificate).all(),
        key=lambda item: (
            item.status != "held",
            -(item.acquired_on.toordinal() if item.acquired_on else 0),
            item.id,
        ),
    )


def build_list(db, today: date | None = None) -> dict:
    rows = [serialize(item, today) for item in _ordered(db)]
    held = [row for row in rows if row["status"] == "held"]

    return {
        "language": [row for row in rows if row["category"] == "language"],
        "job": [row for row in rows if row["category"] == "job"],
        "summary": {
            "held": len(held),
            "planned": len(rows) - len(held),
            "expiring_soon": sum(1 for row in held if row["expiry_state"] == "soon"),
            "expired": sum(1 for row in held if row["expiry_state"] == "expired"),
        },
    }


def relevant(db, flags: list[dict], today: date | None = None) -> list[dict]:
    """공고 경고 옆에 놓을 내 자격. 어학 경고 → 어학, 자격증 경고 → 직무 자격."""
    kinds = {flag["kind"] for flag in flags}
    ordered = None
    groups = []

    for kind, category in FLAG_CATEGORIES.items():
        if kind not in kinds:
            continue

        if ordered is None:
            ordered = _ordered(db)

        groups.append({
            "flag_kind": kind,
            "category": category,
            "category_label": CATEGORY_LABELS[category],
            "certificates": [
                serialize(item, today)
                for item in ordered
                if item.category == category and item.status == "held"
            ],
        })

    return groups
