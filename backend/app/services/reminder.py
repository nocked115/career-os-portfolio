"""알리미 — 날짜가 있는 것을 한 판에.

수현: "오늘 마감 · 역량검사 대비 (10/18 일) 이런 것도
알리미처럼 넣으려고."

**일을 시키는 판이 아니라 알려 주는 판이다.** 시간을 재지 않고,
진행률을 움직이지 않고, 오늘 쓸 수 있는 시간에서 빠지지 않는다.
날짜가 오면 알려 주고 지나가면 사라진다.

알릴 것의 대부분은 **앱이 이미 안다.** 공고 마감, 지원서 마감, 시험일,
학습 단계 마감 — 다 들고 있으면서 각각 다른 화면에 흩어져 있었다.
여기서 모아 한 줄로 세운다. 사람이 적는 것은 앱이 모르는 것뿐이다.
"""
from datetime import date, timedelta

from .. import models


# 며칠 앞까지 알릴 것인가. 더 멀면 알림이 아니라 달력이다.
HORIZON_DAYS = 14


def _row(kind, label, title, due, *, at="", where="", id=None,
         done=False, source="app") -> dict:
    return {
        "id": id,
        "kind": kind,
        "label": label,
        "title": title,
        "due": due,
        "at": at,
        "where": where,
        "done": done,
        # app = 앱이 아는 것(지울 수 없다) · mine = 내가 적은 것
        "source": source,
    }


def gather(db, today: date | None = None, days: int = HORIZON_DAYS) -> dict:
    """오늘부터 앞으로 며칠간 알릴 것 전부."""
    today = today or date.today()
    last = today + timedelta(days=days)

    rows = []

    # --- 내가 적은 것 ---
    for row in (
        db.query(models.Reminder)
        .filter(models.Reminder.done.is_(False))
        .filter(models.Reminder.due >= today)
        .filter(models.Reminder.due <= last)
        .all()
    ):
        rows.append(_row(
            "mine", "적어 둔 것", row.title, row.due,
            at=row.at, where=row.note, id=row.id, source="mine",
        ))

    # --- 공고 · 지원서 마감 (앱이 안다) ---
    from . import today as today_service

    # collect_deadlines 는 날짜가 아니라 **남은 일수**로 돌려준다
    # (days_left). 날짜로 바꿔서 쓴다 — 같은 줄에 세우려면 날짜가 필요하다.
    for item in today_service.collect_deadlines(db, today):
        days_left = item.get("days_left")

        if days_left is None or days_left > days:
            continue

        kind = item.get("kind")

        if kind == "learning_step":
            continue        # 학습 마감은 아래에서 따로 모은다

        where = ""

        if kind == "opportunity":
            row = db.get(models.Opportunity, item.get("id"))
            where = (row.organization or "") if row else ""
        elif kind == "application":
            row = db.get(models.Application, item.get("id"))
            where = (
                (row.opportunity.organization or "")
                if row is not None and row.opportunity is not None else ""
            )

        rows.append(_row(
            "deadline",
            "지원서 마감" if kind == "application" else "공고 마감",
            item.get("title", ""), today + timedelta(days=days_left),
            where=where,
        ))

    # --- 시험 (앱이 안다) ---
    for block in (
        db.query(models.CalendarBlock)
        .filter(models.CalendarBlock.kind == "exam")
        .filter(models.CalendarBlock.date.isnot(None))
        .filter(models.CalendarBlock.date >= today)
        .filter(models.CalendarBlock.date <= last)
        .all()
    ):
        from . import calendar as calendar_service

        rows.append(_row(
            "exam", "시험", block.title, block.date,
            at=calendar_service.format_minute(block.start_minute),
        ))

    # --- 학습 단계 마감 (앱이 안다) ---
    for step in (
        db.query(models.LearningStep)
        .filter(models.LearningStep.due_date.isnot(None))
        .filter(models.LearningStep.due_date >= today)
        .filter(models.LearningStep.due_date <= last)
        .filter(models.LearningStep.status != "completed")
        .all()
    ):
        path = step.learning_path

        rows.append(_row(
            "learning", "학습 마감", step.title, step.due_date,
            where=path.title if path else "",
        ))

    rows.sort(key=lambda row: (row["due"], row["at"] or "99:99", row["title"]))

    by_day: dict[date, list] = {}

    for row in rows:
        by_day.setdefault(row["due"], []).append(row)

    return {
        "today": today,
        "count": len(rows),
        "days": [
            {
                "date": day,
                "days_away": (day - today).days,
                "weekday": "월화수목금토일"[day.weekday()],
                "items": items,
            }
            for day, items in sorted(by_day.items())
        ],
    }


def create(db, title: str, due: date, at: str = "", note: str = "") -> dict:
    row = models.Reminder(
        title=title.strip(), due=due, at=(at or "").strip(),
        note=(note or "").strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return _row("mine", "적어 둔 것", row.title, row.due,
                at=row.at, where=row.note, id=row.id, source="mine")
