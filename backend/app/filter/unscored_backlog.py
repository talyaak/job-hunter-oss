import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    ApplicationStatus,
    IngestionReject,
    IngestionRun,
    IngestionStatus,
    Lead,
    PlatformSource,
    RecruiterType,
    RejectStage,
    UserProfile,
    WorkplaceType,
)
from app.filter.contact_sanitize import build_email_blocklist, sanitize_contact_email
from app.filter.dedupe import DedupeIndex
from app.filter.embeddings import format_similar_examples, retrieve_similar_examples
from app.filter.gemini_scorer import score_job
from app.filter.hard_reject import is_hard_rejected
from app.filter.job_fingerprint import job_fingerprint
from app.filter.location_reject import is_location_rejected
from app.ingestion.linkedin_auth import build_linkedin_client, enrich_description
from app.ingestion.normalizer import RawJob, normalize_job
from app.preferences import get_preferences

log = logging.getLogger(__name__)

QUOTA_RE = re.compile(r"\b429\b|quota", re.I)


@dataclass
class BacklogStats:
    pending: int
    processed: int
    leads_created: int
    scored_rejected: int
    hard_filtered: int
    dismissed: int
    deduped: int
    quota_stopped: bool
    remaining: int


def list_unscored_rejects(db: Session, limit: int | None = None) -> list[IngestionReject]:
    latest_ids = select(func.max(IngestionReject.id)).group_by(IngestionReject.job_url)
    lead_urls = select(Lead.job_url)
    q = (
        select(IngestionReject)
        .where(IngestionReject.id.in_(latest_ids))
        .where(IngestionReject.relevance_score.is_(None))
        .where(IngestionReject.job_url.not_in(lead_urls))
        .order_by(IngestionReject.created_at.desc())
    )
    if limit is not None:
        q = q.limit(limit)
    return list(db.scalars(q).all())


def count_unscored_rejects(db: Session) -> int:
    latest_ids = select(func.max(IngestionReject.id)).group_by(IngestionReject.job_url)
    lead_urls = select(Lead.job_url)
    return db.scalar(
        select(func.count())
        .select_from(IngestionReject)
        .where(IngestionReject.id.in_(latest_ids))
        .where(IngestionReject.relevance_score.is_(None))
        .where(IngestionReject.job_url.not_in(lead_urls))
    ) or 0


def _infer_platform(job_url: str) -> str:
    host = urlparse(job_url).netloc.lower()
    if "linkedin.com" in host:
        return "linkedin"
    if "indeed.com" in host:
        return "indeed"
    if "glassdoor.com" in host:
        return "glassdoor"
    return "google"


def _backlog_run_id(db: Session) -> int:
    run_id = db.scalar(
        select(IngestionRun.id)
        .where(IngestionRun.status == IngestionStatus.completed)
        .order_by(IngestionRun.id.desc())
        .limit(1)
    )
    return run_id or 1


def _log_reject(
    db: Session,
    run_id: int,
    job: RawJob,
    stage: RejectStage,
    reason: str,
    score: int | None = None,
    stack: list | None = None,
) -> None:
    db.add(
        IngestionReject(
            job_title=job.job_title,
            company=job.company,
            job_url=job.job_url,
            reject_stage=stage,
            reject_reason=reason,
            relevance_score=score,
            stack_match=json.dumps(stack) if stack else None,
            ingestion_run_id=run_id,
            created_at=datetime.utcnow(),
        )
    )


def _map_workplace(val: str, hint: str | None) -> WorkplaceType:
    v = (val or hint or "unknown").lower()
    for wt in WorkplaceType:
        if wt.value == v:
            return wt
    return WorkplaceType.unknown


def _to_raw_job(row: IngestionReject, description: str = "") -> RawJob:
    return normalize_job(
        row.job_title or "",
        row.company or "",
        row.job_url,
        description,
        _infer_platform(row.job_url),
    )


def _fetch_description(job_url: str, li_client) -> str:
    if "linkedin.com" in job_url and li_client:
        return enrich_description(job_url, li_client) or ""
    return ""


def _is_quota_error(msg: str) -> bool:
    return bool(QUOTA_RE.search(msg))


def _create_lead(
    db: Session,
    run_id: int,
    job: RawJob,
    result: dict,
    score: int,
    email_blocklist: set[str],
    dedupe_index: DedupeIndex,
) -> None:
    stack = result.get("stack_match") or []
    eval_blob = result.get("match_evaluation") or {}
    db.add(
        Lead(
            date_posted=job.date_posted,
            job_title=job.job_title,
            company=job.company,
            platform_source=PlatformSource(job.platform_source),
            submission_method=result.get("submission_method", job.submission_method),
            recruiter_type=RecruiterType(result.get("recruiter_type", "direct")),
            workplace_type=_map_workplace(result.get("workplace_type"), job.workplace_type_hint),
            company_size=result.get("company_size", "Unknown"),
            product_vertical=result.get("product_vertical", "Unknown"),
            contact_name=result.get("contact_name"),
            contact_linkedin_url=result.get("contact_linkedin_url"),
            contact_email=sanitize_contact_email(
                result.get("contact_email") or job.contact_email, email_blocklist
            ),
            match_reason=result.get("match_reason", ""),
            match_evaluation=json.dumps(eval_blob),
            stack_match=json.dumps(stack),
            relevance_score=score,
            application_status=ApplicationStatus.saved,
            job_url=job.job_url,
            description=job.description,
            ingestion_run_id=run_id,
            created_at=datetime.utcnow(),
        )
    )
    dedupe_index.register_lead(job.job_url, job.company, job.job_title)


def process_unscored_backlog(
    db: Session,
    *,
    mode: str = "auto",
    limit: int = 20,
) -> BacklogStats:
    """Process awaiting-score backlog: hard-filter, score, or graveyard-dismiss."""
    if mode not in ("auto", "score", "dismiss"):
        raise ValueError("mode must be auto, score, or dismiss")

    pending = count_unscored_rejects(db)
    rows = list_unscored_rejects(db, limit=limit)
    run_id = _backlog_run_id(db)

    profile = db.get(UserProfile, 1)
    if mode == "score" and (not profile or not profile.cv_text or not profile.profile_markdown):
        raise ValueError("Upload CV and profile before scoring backlog")

    dedupe_index = DedupeIndex(db)
    email_blocklist = build_email_blocklist(db)
    li_client = build_linkedin_client() if mode != "dismiss" else None

    stats = BacklogStats(
        pending=pending,
        processed=0,
        leads_created=0,
        scored_rejected=0,
        hard_filtered=0,
        dismissed=0,
        deduped=0,
        quota_stopped=False,
        remaining=pending,
    )

    prefs = get_preferences(db)
    for row in rows:
        if stats.quota_stopped:
            break

        job = _to_raw_job(row)
        stats.processed += 1

        if mode == "dismiss":
            _log_reject(db, run_id, job, RejectStage.llm_score, "Backlog dismissed", score=0)
            stats.dismissed += 1
            db.commit()
            continue

        dup, dup_reason = dedupe_index.is_duplicate(job.job_url, job.company, job.job_title)
        if dup:
            _log_reject(db, run_id, job, RejectStage.dedupe, dup_reason or "Duplicate", score=0)
            stats.deduped += 1
            db.commit()
            continue

        rejected, reason = is_hard_rejected(job.job_title, job.description, prefs, job.company)
        if rejected:
            _log_reject(db, run_id, job, RejectStage.hard_title, reason or "", score=0)
            stats.hard_filtered += 1
            dedupe_index.register_scored_reject(job.company, job.job_title)
            db.commit()
            continue

        description = job.description or _fetch_description(job.job_url, li_client)
        if description:
            job.description = description

        rejected, reason = is_location_rejected(job.job_title, job.description, None, prefs)
        if rejected:
            _log_reject(db, run_id, job, RejectStage.location, reason or "", score=0)
            stats.hard_filtered += 1
            db.commit()
            continue

        if mode == "auto" and not job.description.strip():
            _log_reject(
                db,
                run_id,
                job,
                RejectStage.llm_score,
                "Backlog dismissed: description unavailable",
                score=0,
            )
            stats.dismissed += 1
            db.commit()
            continue

        if not settings.gemini_api_key:
            _log_reject(db, run_id, job, RejectStage.llm_score, "Backlog dismissed: GEMINI_API_KEY not set", score=0)
            stats.dismissed += 1
            db.commit()
            continue

        similar_examples = ""
        if settings.embedding_retrieve_examples > 0:
            try:
                similar_examples = format_similar_examples(retrieve_similar_examples(db, job))
            except Exception as e:
                log.warning("[Backlog] Similar-example retrieval failed: %s", e)

        try:
            result = score_job(job, profile.cv_text or "", profile.profile_markdown or "", similar_examples, prefs)
        except Exception as e:
            err = str(e)
            if _is_quota_error(err):
                stats.quota_stopped = True
                db.commit()
                break
            _log_reject(db, run_id, job, RejectStage.llm_score, err, score=0)
            stats.scored_rejected += 1
            dedupe_index.register_scored_reject(job.company, job.job_title)
            db.commit()
            continue

        score = int(result.get("relevance_score", 0))
        stack = result.get("stack_match") or []
        eval_blob = result.get("match_evaluation") or {}
        reject_reason = result.get("match_reason", "Below threshold")
        if result.get("hard_reject_override"):
            dbs = eval_blob.get("deal_breakers") or []
            reject_reason = f"Deal breakers: {'; '.join(dbs)}" if dbs else reject_reason

        if score < prefs.score_threshold or result.get("hard_reject_override"):
            _log_reject(db, run_id, job, RejectStage.llm_score, reject_reason, score, stack)
            stats.scored_rejected += 1
            dedupe_index.register_scored_reject(job.company, job.job_title)
            db.commit()
            continue

        fp = job_fingerprint(job.company, job.job_title)
        if fp in dedupe_index.lead_fingerprints:
            _log_reject(
                db,
                run_id,
                job,
                RejectStage.dedupe,
                f"Duplicate role already in leads: {job.company} / {job.job_title}",
                score=0,
            )
            stats.deduped += 1
            db.commit()
            continue

        _create_lead(db, run_id, job, result, score, email_blocklist, dedupe_index)
        stats.leads_created += 1
        db.commit()

    stats.remaining = count_unscored_rejects(db)
    log.info(
        "[Backlog] processed=%s leads=%s rejected=%s hard=%s dismissed=%s deduped=%s remaining=%s quota_stop=%s",
        stats.processed,
        stats.leads_created,
        stats.scored_rejected,
        stats.hard_filtered,
        stats.dismissed,
        stats.deduped,
        stats.remaining,
        stats.quota_stopped,
    )
    return stats
