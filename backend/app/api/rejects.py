import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import IngestionReject, Lead, RejectStage
from app.db.session import get_db
from app.filter.unscored_backlog import BacklogStats, count_unscored_rejects, process_unscored_backlog
from app.ingestion.pipeline import is_pipeline_running
from app.schemas import RejectListOut, RejectOut, UnscoredProcessOut

router = APIRouter(prefix="/api/rejects", tags=["rejects"])


def _parse_stack(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _latest_ids_subquery(stage: RejectStage | None, scored: bool | None = None):
    q = select(func.max(IngestionReject.id)).group_by(IngestionReject.job_url)
    if stage:
        q = q.where(IngestionReject.reject_stage == stage)
    if scored is True:
        q = q.where(IngestionReject.relevance_score.is_not(None))
    elif scored is False:
        q = q.where(IngestionReject.relevance_score.is_(None))
    return q


def _to_items(rows) -> list[RejectOut]:
    return [
        RejectOut(
            id=r.id,
            job_title=r.job_title,
            company=r.company,
            job_url=r.job_url,
            reject_stage=r.reject_stage.value,
            reject_reason=r.reject_reason,
            relevance_score=r.relevance_score,
            stack_match=_parse_stack(r.stack_match),
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("", response_model=RejectListOut)
def list_rejects(
    min_score: int | None = Query(None, ge=0, le=100),
    max_score: int | None = Query(None, ge=0, le=100),
    stage: str | None = Query(None),
    scored: bool | None = Query(None, description="false = never scored (quota/errors)"),
    db: Session = Depends(get_db),
):
    if scored is False:
        latest_ids = select(func.max(IngestionReject.id)).group_by(IngestionReject.job_url)
        lead_urls = select(Lead.job_url)
        q = (
            select(IngestionReject)
            .where(IngestionReject.id.in_(latest_ids))
            .where(IngestionReject.relevance_score.is_(None))
            .where(IngestionReject.job_url.not_in(lead_urls))
        )
        rows = db.scalars(
            q.order_by(IngestionReject.created_at.desc())
        ).all()
        items = _to_items(rows)
        return RejectListOut(items=items, total=len(items))

    score_filter = min_score is not None or max_score is not None
    stage_enum: RejectStage | None = None
    if stage:
        try:
            stage_enum = RejectStage(stage)
        except ValueError:
            pass
    elif score_filter:
        stage_enum = RejectStage.llm_score

    latest_ids = _latest_ids_subquery(stage_enum, scored=True if score_filter else None)
    q = select(IngestionReject).where(IngestionReject.id.in_(latest_ids))

    if stage_enum:
        q = q.where(IngestionReject.reject_stage == stage_enum)

    if min_score is not None:
        q = q.where(IngestionReject.relevance_score.is_not(None))
        q = q.where(IngestionReject.relevance_score >= min_score)
    if max_score is not None:
        q = q.where(IngestionReject.relevance_score.is_not(None))
        q = q.where(IngestionReject.relevance_score <= max_score)

    rows = db.scalars(
        q.order_by(IngestionReject.relevance_score.desc().nulls_last(), IngestionReject.created_at.desc())
    ).all()
    return RejectListOut(items=_to_items(rows), total=len(rows))


@router.get("/unscored/count")
def unscored_count(db: Session = Depends(get_db)):
    return {"count": count_unscored_rejects(db)}


@router.post("/unscored/process", response_model=UnscoredProcessOut)
def process_unscored(
    mode: str = Query("auto", description="auto | score | dismiss"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if is_pipeline_running():
        raise HTTPException(status_code=409, detail="Sync in progress — try again when finished")
    try:
        stats: BacklogStats = process_unscored_backlog(db, mode=mode, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return UnscoredProcessOut(**stats.__dict__)
