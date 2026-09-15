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

    scheduler.start()

    print("[Career OS] Scheduler started.")