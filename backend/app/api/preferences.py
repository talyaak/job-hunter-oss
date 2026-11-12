from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.preferences import Preferences, get_preferences, save_preferences

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=Preferences)
def read_preferences(db: Session = Depends(get_db)):
    return get_preferences(db)


@router.put("", response_model=Preferences)
def write_preferences(body: Preferences, db: Session = Depends(get_db)):
    saved = save_preferences(db, body)
    # cron hours/timezone may have changed
    from app.config import settings

    if settings.ingestion_enabled:
        from app.scheduler.cron import scheduler, schedule_jobs

        if scheduler is not None:
            schedule_jobs(saved)
    return saved
