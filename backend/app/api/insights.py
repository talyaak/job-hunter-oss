"""Aggregate stats used by the dashboard and by the `tips` agent skill to coach preference changes."""

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ApplicationStatus, IngestionReject, IngestionRun, Lead, RejectStage
from app.db.session import get_db
from app.preferences import get_preferences

router = APIRouter(prefix="/api/insights", tags=["insights"])


def _histogram(scores: list[int]) -> dict[str, int]:
    buckets = {"0-49": 0, "50-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
    for s in scores:
        if s < 50:
            buckets["0-49"] += 1
        elif s < 70:
            buckets["50-69"] += 1
        elif s < 80:
            buckets["70-79"] += 1
        elif s < 90:
            buckets["80-89"] += 1
        else:
            buckets["90-100"] += 1
    return buckets


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    prefs = get_preferences(db)

    lead_scores = [s for s in db.scalars(select(Lead.relevance_score)) if s is not None]
    reject_rows = db.execute(
        select(IngestionReject.reject_stage, IngestionReject.reject_reason, IngestionReject.relevance_score)
    ).all()
    by_stage = Counter(stage.value for stage, _, _ in reject_rows)
    scored_rejects = [score for stage, _, score in reject_rows if stage == RejectStage.llm_score and score]
    near_miss = [s for s in scored_rejects if prefs.score_threshold - 10 <= s < prefs.score_threshold]

    reason_counter: Counter[str] = Counter()
    for stage, reason, _ in reject_rows:
        if stage in (RejectStage.hard_title, RejectStage.location):
            reason_counter[reason] += 1

    status_counts = {
        s.value: db.scalar(select(func.count()).select_from(Lead).where(Lead.application_status == s)) or 0
        for s in ApplicationStatus
    }
    source_rows = db.execute(select(Lead.platform_source, func.count()).group_by(Lead.platform_source)).all()
    last_runs = db.scalars(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(5)).all()

    return {
        "threshold": prefs.score_threshold,
        "leads": {
            "total": len(lead_scores),
            "score_histogram": _histogram(lead_scores),
            "by_status": status_counts,
            "by_source": {src.value: n for src, n in source_rows},
        },
        "rejects": {
            "total": len(reject_rows),
            "by_stage": dict(by_stage),
            "scored_near_miss_count": len(near_miss),
            "top_filter_reasons": reason_counter.most_common(8),
        },
        "recent_runs": [
            {
                "id": r.id,
                "status": r.status.value,
                "raw_count": r.raw_count,
                "passed_count": r.passed_count,
                "started_at": r.started_at.isoformat() if r.started_at else None,
            }
            for r in last_runs
        ],
        "preferences": prefs.model_dump(),
    }
