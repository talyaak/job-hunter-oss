from datetime import datetime
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngestionRun, IngestionStatus, IngestionTrigger
from app.db.session import SessionLocal, get_db
from app.ingestion.pipeline import get_current_run_id, is_pipeline_running, run_pipeline
from app.ingestion.sync_guard import recover_orphaned_sync_runs
from app.schemas import IngestionRunOut, SyncStartOut, SyncStatusOut
from app.sync_hub import hub

router = APIRouter(prefix="/api/sync", tags=["sync"])
log = logging.getLogger(__name__)


def _run_bg():
    db = SessionLocal()
    try:
        log.info("[Manual] Ingestion started")
        run_pipeline(db, IngestionTrigger.manual)
        log.info("[Manual] Ingestion completed")
    except Exception as e:
        log.error("Ingestion failed: %s", e)
    finally:
        db.close()


@router.websocket("/ws")
async def sync_ws(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)


@router.post("", response_model=SyncStartOut, status_code=202)
def start_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    recover_orphaned_sync_runs(db)

    if is_pipeline_running():
        raise HTTPException(409, "Sync already running")

    running = db.scalar(select(IngestionRun).where(IngestionRun.status == IngestionStatus.running))
    if running:
        raise HTTPException(409, "Sync already running")

    background_tasks.add_task(_run_bg)
    run_id = get_current_run_id() or 0
    return SyncStartOut(run_id=run_id)


@router.get("/status", response_model=SyncStatusOut)
def sync_status(db: Session = Depends(get_db)):
    recover_orphaned_sync_runs(db)
    current = db.scalar(
        select(IngestionRun).where(IngestionRun.status == IngestionStatus.running).order_by(IngestionRun.id.desc())
    )
    last = db.scalar(
        select(IngestionRun)
        .where(IngestionRun.status == IngestionStatus.completed)
        .order_by(IngestionRun.finished_at.desc())
    )
    return SyncStatusOut(current=current, last_completed=last)


@router.get("/latest", response_model=IngestionRunOut | None)
def sync_latest(db: Session = Depends(get_db)):
    return db.scalar(
        select(IngestionRun)
        .where(IngestionRun.status == IngestionStatus.completed)
        .order_by(IngestionRun.finished_at.desc())
    )
