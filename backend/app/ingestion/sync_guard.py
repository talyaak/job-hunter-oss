from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngestionRun, IngestionStatus
from app.ingestion.pipeline import is_pipeline_running


def recover_orphaned_sync_runs(db: Session) -> int:
    """Mark stale running rows failed when the in-process pipeline is not active."""
    if is_pipeline_running():
        return 0
    rows = list(db.scalars(select(IngestionRun).where(IngestionRun.status == IngestionStatus.running)))
    if not rows:
        return 0
    for run in rows:
        run.status = IngestionStatus.failed
        run.error_message = "Interrupted (server restarted or process crashed)"
        run.finished_at = datetime.utcnow()
    db.commit()
    return len(rows)
