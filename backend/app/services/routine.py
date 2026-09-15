"""루틴 — 정한 요일마다 하는 일 (코테 30분 · coding rehab 30분).

오늘 계획은 루틴의 시간을 먼저 떼어 두고 남은 시간으로 나머지를 고른다
(today.generate_plan). 여기는 루틴이 오늘 할 차례인지, 이번 주에 얼마나
했는지, 목표를 올려도 되는지를 센다.

목표를 저절로 올리지 않는다. "늘려 간다" 는 사람이 정하고, 앱은 기록으로
근거만 댄다 — 지난 7일 중 할 차례였던 날이 5일 이상이고 그 날들 중 5일
이상 목표를 채웠으면 한 개 올리기를 **제안** 한다.

이 모듈은 today 서비스를 임포트하지 않는다 (today 가 이쪽을 부른다).
"""

from datetime import date, timedelta

from .. import models


WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]

SUGGEST_WINDOW_DAYS = 7
SUGGEST_MIN_DAYS = 5


def weekdays_of(routine) -> list[int]:
    return sorted({int(ch) for ch in (routine.weekdays or "") if ch.isdigit() and int(ch) < 7})


def encode_weekdays(values) -> str:
    days = sorted(set(values))
    if not days or any(day < 0 or day > 6 for day in days):
        raise ValueError("요일은 월(0)부터 일(6) 사이에서 하나 이상 골라 주세요.")
    return "".join(str(day) for day in days)


def weekday_label(routine) -> str:
    days = weekdays_of(routine)
    if len(days) == 7:
        return "매일"
    if days == [0, 1, 2, 3, 4]:
        return "평일"
    if days == [5, 6]:
        return "주말"
    return " · ".join(WEEKDAY_NAMES[day] for day in days)


def is_due(routine, day: date) -> bool:
    return routine.active and day.weekday() in weekdays_of(routine)


def _started_on(routine) -> date | None:
    created = routine.created_at
    return created.date() if created is not None else None


def _was_due(routine, day: date) -> bool:
    """그날이 할 차례였는가. 루틴을 만들기 전 날은 차례가 아니다.

    만든 날 화면에 "이번 주 1일 중 0일" 이 떴다 — 월요일에 없던 루틴을
    안 한 것으로 셌다.
    """
    started = _started_on(routine)
    if started is not None and day < started:
        return False
    return day.weekday() in weekdays_of(routine)


def _logs_by_date(routine) -> dict:
    return {log.log_date: log for log in routine.logs}


def target_text(routine) -> str | None:
    if not routine.target_count:
        return None
    return f"{routine.target_count}{routine.unit_label or '개'}"


def week_summary(routine, today: date) -> dict:
    """이번 주(월요일부터). 오늘은 이미 했을 때만 센다 — 하루가 끝나지 않았다."""
    logs = _logs_by_date(routine)
    monday = today - timedelta(days=today.weekday())

    due = done = 0
    day = monday
    while day <= today:
        if _was_due(routine, day):
            if day < today or day in logs:
                due += 1
                if day in logs:
                    done += 1
        day += timedelta(days=1)

    return {"due": due, "done": done}


def suggestion(routine, today: date) -> dict | None:
    """목표 올리기 제안. 근거 숫자와 함께. 없으면 None."""
    if not routine.target_count:
        return None

    logs = _logs_by_date(routine)
    due_days = [
        today - timedelta(days=offset)
        for offset in range(1, SUGGEST_WINDOW_DAYS + 1)
        if _was_due(routine, today - timedelta(days=offset))
    ]
    met = [
        day for day in due_days
        if day in logs and (logs[day].count or 0) >= routine.target_count
    ]

    if len(due_days) < SUGGEST_MIN_DAYS or len(met) < SUGGEST_MIN_DAYS:
        return None

    unit = routine.unit_label or "개"
    return {
        "to": routine.target_count + 1,
        "evidence": (
            f"지난 7일 중 할 차례였던 {len(due_days)}일 가운데 "
            f"{len(met)}일 {routine.target_count}{unit}를 채웠어요."
        ),
    }


def recent(routine, today: date, days: int = 7) -> list[dict]:
    logs = _logs_by_date(routine)
    rows = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        log = logs.get(day)
        rows.append({
            "date": day,
            "weekday": WEEKDAY_NAMES[day.weekday()],
            "due": _was_due(routine, day),
            "count": log.count if log else None,
            "done": log is not None,
        })
    return rows


def next_step(path):
    """경로의 다음 단계 — 진행 중인 것 먼저, 그다음 순서대로."""
    if path is None:
        return None
    return next(
        (
            step
            for step in sorted(path.steps, key=lambda s: (s.status != "in_progress", s.position))
            if step.status != "completed"
        ),
        None,
    )


def serialize(routine, today: date) -> dict:
    log = _logs_by_date(routine).get(today)
    step = next_step(routine.learning_path)

    return {
        "id": routine.id,
        "title": routine.title,
        "minutes": routine.minutes,
        "weekdays": weekdays_of(routine),
        "weekday_label": weekday_label(routine),
        "target_count": routine.target_count,
        "unit_label": routine.unit_label,
        "target_text": target_text(routine),
        "learning_path": (
            {"id": routine.learning_path.id, "title": routine.learning_path.title}
            if routine.learning_path is not None
            else None
        ),
        "next_step": {"id": step.id, "title": step.title} if step else None,
        "active": routine.active,
        "note": routine.note,
        "due_today": is_due(routine, today),
        "today_log": {"count": log.count} if log else None,
        "week": week_summary(routine, today),
        "recent": recent(routine, today),
        "suggestion": suggestion(routine, today),
    }


def task_summary(routine) -> dict:
    return {
        "target_count": routine.target_count,
        "unit_label": routine.unit_label,
    }


def plan_candidates(db, today: date, exclude: set) -> list[dict]:
    """오늘 할 차례인 루틴. 오늘 이미 기록했거나 계획에서 끝낸 것은 뺀다."""
    candidates = []

    routines = (
        db.query(models.Routine)
        .filter(models.Routine.active.is_(True))
        .order_by(models.Routine.id)
        .all()
    )

    for routine in routines:
        if routine.id in exclude or not is_due(routine, today):
            continue
        if today in _logs_by_date(routine):
            continue

        step = next_step(routine.learning_path)
        week = week_summary(routine, today)

        parts = [f"{weekday_label(routine)} 하는 일"]
        if target_text(routine):
            parts.append(f"목표 {target_text(routine)}")
        if week["due"]:
            parts.append(f"이번 주 {week['due']}일 중 {week['done']}일 함")

        candidates.append({
            "task_type": "routine",
            "title": f"{routine.title} — {step.title}" if step else routine.title,
            "minutes": routine.minutes,
            "reason": " · ".join(parts) + ".",
            "routine_id": routine.id,
            "learning_step_id": step.id if step else None,
            "urgent": False,
        })

    return candidates


def record(db, routine, day: date, count: int | None = None):
    """그날 했다고 남긴다. 개수를 안 주면 목표만큼 한 것으로 본다."""
    log = _logs_by_date(routine).get(day)

    if log is None:
        log = models.RoutineLog(routine_id=routine.id, log_date=day)
        db.add(log)
        routine.logs.append(log)

    log.count = count if count is not None else routine.target_count
    log.minutes = routine.minutes
    return log


def unrecord(db, routine, day: date) -> bool:
    log = _logs_by_date(routine).get(day)
    if log is None:
        return False
    routine.logs.remove(log)
    db.delete(log)
    return True


def describe_log(routine, log) -> str:
    if log.count is not None and routine.target_count:
        unit = routine.unit_label or "개"
        return f"{routine.title} {log.count}{unit} 기록 (목표 {routine.target_count}{unit})"
    return f"{routine.title} 오늘 한 것으로 기록"
