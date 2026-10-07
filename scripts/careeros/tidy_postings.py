"""쌓인 공고를 치운다 — 중복 묶기와 마감 내리기. 일주일에 한 번쯤.

  python3 tidy_postings.py          무엇을 치울지 보여주기만 한다
  python3 tidy_postings.py --apply  실제로 치운다

수집원이 다섯이라 같은 공고가 여러 번 들어온다. 한 회사가 요구하는
스킬이 네 배로 세어지면 수요 비율이 통째로 틀어진다.

**지원서가 걸린 공고는 건드리지 않는다.** 치우면 그 지원서가 어느
공고인지 화면에서 사라진다 — 2026-10-06 에 실제로 한 번 그렇게 깨졌다.

**원문을 다시 받아오지 않는다.** 공고 대부분이 url 이 비어 있어 "들어가
보고 판단" 이 불가능하고, 되는 것도 사이트마다 마감 표시가 달라 규칙으로
읽을 수 없다. 이미 저장된 마감일로만 판단한다.

지우지 않는다 — 중복은 보관함(archived), 마감은 닫음(closed)으로 상태만
바꾼다. 잘못 묶였으면 화면에서 되돌리면 된다.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
VENV_PYTHON = BACKEND / ".venv" / "bin" / "python"

if VENV_PYTHON.is_file() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

os.environ.setdefault("CAREER_OS_DATABASE_URL", f"sqlite:///{BACKEND / 'career_os.db'}")
sys.path.insert(0, str(BACKEND))

from app.database import SessionLocal  # noqa: E402
from app.services import tidy  # noqa: E402


def main():
    apply = "--apply" in sys.argv

    db = SessionLocal()

    try:
        plan = tidy.preview(db)

        if plan["duplicates"]:
            print(f"■ 같은 공고로 보이는 묶음 {len(plan['duplicates'])}개\n")
            for item in plan["duplicates"]:
                print(f"  {item['organization']} — {item['title'][:44]}")
                print(f"     남김  #{item['keep']['id']} ({item['keep']['source']})")
                for row in item["drop"]:
                    print(f"     보관함 #{row['id']} ({row['source']})")
                for kept in item["kept_for_applications"]:
                    print(f"     그대로 #{kept} — 지원서가 걸려 있음")
                print()
        else:
            print("■ 중복으로 보이는 공고 없음\n")

        if plan["far_events"]:
            print(f"■ 서울 밖 채용 행사 {len(plan['far_events'])}개 — 못 가는 자리\n")
            for row in plan["far_events"]:
                print(f"  {row['title'][:46]}")
                if row["location"]:
                    print(f"     {row['location'][:60]}")
            print()

        if plan["expired"]:
            print(f"■ 마감이 지났는데 안 닫힌 것 {len(plan['expired'])}개\n")
            for row in plan["expired"][:12]:
                mark = " (지원함)" if row["has_application"] else ""
                print(f"  {row['days_past']:>4}일 지남  {row['deadline']}  "
                      f"{row['organization'][:10]:12} {row['title'][:34]}{mark}")
            if len(plan["expired"]) > 12:
                print(f"  … 그 밖 {len(plan['expired']) - 12}개")
            print()
        else:
            print("■ 마감 지난 공고 없음\n")

        print(f"치울 것: 보관함 {plan['will_archive']}개 · 닫음 {plan['will_close']}개")

        if not apply:
            print("\n보여주기만 했어요. 실제로 치우려면:  python3 tidy_postings.py --apply")
            return

        if plan["will_archive"] + plan["will_close"] == 0:
            return

        tidy.apply(db)
        print("\n치웠습니다. 지우지 않고 상태만 바꿨어요 — 화면에서 되돌릴 수 있습니다.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
