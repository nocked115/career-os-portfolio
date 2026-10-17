#!/usr/bin/env python3
"""보관함 정리 — 지난 까닭 되살리기, 끝난 채용 행사 지우기.

수현: "마감 지난 건 마감 지남으로 바꿔줘. 그리고 채용 행사는 (보관함에
있는 거) 이건 그냥 다 지워도 될 듯."

두 가지를 한다.

1. **마감 지남으로 고쳐 적기.** 치우기가 까닭을 남기기 전(커밋 139)에
   내려간 줄은 전부 "직접 닫음" 으로 보인다. 수현이 손으로 닫은 것이
   아니라 마감이 지나 내려간 것들이다. 마감일이 **이미 지난** 줄에만
   적는다 — 마감일이 없거나 아직 안 지난 줄은 정말 손으로 닫았을 수
   있어서 건드리지 않는다.

2. **끝난 채용 행사 지우기.** 이 앱은 원래 지우지 않고 상태만 바꾼다.
   까닭이 남아야 "이 스킬 공고 4건 중 3건이 석사 요구" 같은 말을 할 수
   있어서다. 그런데 채용 행사는 애초에 수요 계산에서 빠져 있고
   (market.DEMAND_OFF_TYPES), 지난 행사는 다시 갈 수도 없다. 남겨도
   아무것도 말해 주지 않는 줄이라 지운다.

   **지원서가 걸린 줄은 지우지 않는다.** 지우면 그 지원서가 어느
   공고였는지 화면에서 사라진다.

기본은 미리보기다. 실제로 바꾸려면 --apply 를 준다.
"""
import argparse
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

# app.database 의 기본값은 "sqlite:///./career_os.db" — **지금 폴더** 기준이다.
# 저장소 루트에서 돌리면 빈 DB 를 새로 만들고 "no such table" 로 죽는다.
# 실제로 그랬다. 어디서 돌리든 같은 파일을 보게 못 박는다.
os.environ.setdefault(
    "CAREER_OS_DATABASE_URL", f"sqlite:///{os.path.join(BACKEND, 'career_os.db')}"
)

from app.database import SessionLocal          # noqa: E402
from app import models                          # noqa: E402


def past_due(db):
    """마감이 이미 지났는데 까닭이 안 적힌 줄."""
    return [
        row for row in db.query(models.Opportunity)
        .filter(models.Opportunity.status == "closed")
        .filter(models.Opportunity.tidied_reason == "")
        .all()
        if row.deadline is not None and row.deadline < datetime.now()
    ]


def dead_events(db):
    """보관함에 들어간 채용 행사. 지원서가 걸린 것은 뺀다."""
    return [
        row for row in db.query(models.Opportunity)
        .filter(models.Opportunity.opportunity_type == "job_event")
        .filter(models.Opportunity.status.in_(("archived", "closed")))
        .all()
        if not row.applications
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="실제로 바꾼다")
    args = parser.parse_args()

    print(f"데이터 파일: {os.environ['CAREER_OS_DATABASE_URL']}\n")

    db = SessionLocal()

    due = past_due(db)
    events = dead_events(db)

    print(f"마감 지남으로 고쳐 적을 줄: {len(due)}건")
    for row in due[:5]:
        print(f"  {row.id:4} {row.organization or '?':12} {row.title[:38]}"
              f"  (마감 {row.deadline:%Y-%m-%d})")
    if len(due) > 5:
        print(f"  … 그리고 {len(due) - 5}건")

    print(f"\n지울 채용 행사: {len(events)}건")
    for row in events[:5]:
        print(f"  {row.id:4} {row.title[:46]}")
    if len(events) > 5:
        print(f"  … 그리고 {len(events) - 5}건")

    kept = (
        db.query(models.Opportunity)
        .filter(models.Opportunity.opportunity_type == "job_event")
        .filter(~models.Opportunity.status.in_(("archived", "closed")))
        .count()
    )
    print(f"\n안 건드리는 행사(보관함 밖): {kept}건")

    if not args.apply:
        print("\n미리보기입니다. 실제로 바꾸려면 --apply 를 주세요.")
        return

    for row in due:
        row.tidied_reason = f"마감 지남 — {row.deadline:%Y-%m-%d}"

    for row in events:
        db.delete(row)

    db.commit()
    print(f"\n고쳐 적음 {len(due)}건 · 지움 {len(events)}건.")


if __name__ == "__main__":
    main()
