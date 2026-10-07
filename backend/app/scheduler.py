from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from .database import SessionLocal
from .automation import run_career_automation


scheduler = BackgroundScheduler()

automation_status = {
    "last_run_at": None,
    "last_status": "never_run",
    "last_error": None,
}


def scheduled_career_update():
    db = SessionLocal()

    try:
        print("[Career OS] Starting scheduled automation...")

        result = run_career_automation(db)

        automation_status["last_run_at"] = (
            datetime.now().isoformat()
        )

        automation_status["last_status"] = (
            result["status"]
        )

        automation_status["last_error"] = None

        print(
            "[Career OS] Automation completed:",
            result["status"]
        )

    except Exception as error:
        automation_status["last_run_at"] = (
            datetime.now().isoformat()
        )

        automation_status["last_status"] = "failed"

        automation_status["last_error"] = str(error)

        print(
            "[Career OS] Automation failed:",
            error
        )

    finally:
        db.close()


# 뜰 때마다 한 번 수집한다. 이 분(分) 안에 이미 돌았으면 건너뛴다 —
# 고치다가 서버를 연달아 다시 띄우는 동안 바깥에 같은 요청을 몇 번씩
# 보내지 않으려는 것뿐이다. 하루에 한 번 띄우든 다섯 번 띄우든 실제로는
# 매번 돈다.
CATCH_UP_AFTER_MINUTES = 30


def _minutes_since_last_run(db) -> float | None:
    """마지막 수집으로부터 몇 분. 한 번도 안 돌았으면 None."""
    from . import models

    last = (
        db.query(models.CollectorRun)
        .order_by(models.CollectorRun.ran_at.desc())
        .first()
    )

    if last is None or last.ran_at is None:
        return None

    return (datetime.now() - last.ran_at).total_seconds() / 60


def catch_up_if_stale():
    """뜰 때마다 한 번 수집한다.

    매일 08:00 cron 은 **그 시각에 서버가 켜져 있어야** 돈다. 배포본은
    24시간 떠 있었지만 노트북은 아니다. 로컬로 옮긴 뒤 수집이 사흘간
    한 번도 안 돌았다 — 아침 8시에 노트북이 닫혀 있었기 때문이다.

    그래서 시각이 아니라 **노트북을 켜는 때**에 맞춘다. 30분 안에 이미
    돌았으면 건너뛰는데, 그건 고치다가 서버를 연달아 다시 띄우는 경우만
    막으려는 것이다.
    """
    db = SessionLocal()

    try:
        minutes = _minutes_since_last_run(db)
    finally:
        db.close()

    if minutes is not None and minutes < CATCH_UP_AFTER_MINUTES:
        print(f"[Career OS] {minutes:.0f}분 전에 수집했어요 — 건너뜁니다.")
        return

    when = "한 번도 안 돌았어요" if minutes is None else f"{minutes / 60:.0f}시간 전"
    print(f"[Career OS] 마지막 수집: {when} — 지금 수집합니다.")

    scheduled_career_update()


def start_scheduler():
    if scheduler.running:
        return

    scheduler.add_job(
        scheduled_career_update,
        trigger="cron",
        hour=8,
        minute=0,
        id="career_os_update",
        replace_existing=True
    )

    # 따라잡기는 **백그라운드로** 돌린다. 바깥 요청이 여럿이라
    # 여기서 기다리면 서버가 그만큼 늦게 뜬다.
    scheduler.add_job(catch_up_if_stale, trigger="date", id="career_os_catch_up")

    scheduler.start()

    print("[Career OS] Scheduler started.")