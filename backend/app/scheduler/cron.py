import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.db.models import IngestionTrigger
from app.db.session import SessionLocal
from app.ingestion.pipeline import run_pipeline
from app.preferences import Preferences, get_preferences

log = logging.getLogger(__name__)
scheduler: AsyncIOScheduler | None = None


def _cron_job(hour: int):
    db = SessionLocal()
    try:
        log.info("[Cron %02d:00] Ingestion started", hour)
        run_pipeline(db, IngestionTrigger.cron)
        log.info("[Cron %02d:00] Ingestion completed", hour)
    except Exception as e:
        log.error("[Cron %02d:00] Failed: %s", hour, e)
    finally:
        db.close()


def _timezone(prefs: Preferences) -> str:
    return prefs.timezone or settings.cron_timezone or "UTC"


def schedule_jobs(prefs: Preferences | None = None) -> list[str]:
    """(Re)register cron jobs from preferences. Returns the job ids."""
    global scheduler
    prefs = prefs or get_preferences()
    tz = _timezone(prefs)
    if scheduler is None:
        scheduler = AsyncIOScheduler(timezone=tz)
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)
    ids = []
    for hour in prefs.cron_hours:
        job_id = f"ingest-{hour}"
        scheduler.add_job(
            _cron_job, CronTrigger(hour=hour, minute=0, timezone=tz), args=[hour], id=job_id, replace_existing=True
        )
        ids.append(job_id)
    return ids


def start_scheduler():
    schedule_jobs()
    if scheduler is not None and not scheduler.running:
        scheduler.start()


def scheduler_status() -> dict:
    if scheduler is None:
        return {"running": False, "jobs": []}
    return {
        "running": bool(scheduler.running),
        "jobs": [
            {"id": j.id, "next_run": getattr(j, "next_run_time", None) and j.next_run_time.isoformat()}
            for j in scheduler.get_jobs()
        ],
    }
