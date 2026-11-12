import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.sync_hub import hub

from app.db.models import (
    ApplicationStatus,
    IngestionReject,
    IngestionRun,
    IngestionStatus,
    IngestionTrigger,
    Lead,
    PlatformSource,
    RecruiterType,
    RejectStage,
    UserProfile,
    WorkplaceType,
)
from app.filter.contact_sanitize import build_email_blocklist, sanitize_contact_email
from app.filter.dedupe import DedupeIndex
from app.filter.job_fingerprint import job_fingerprint
from app.filter.embeddings import (
    build_profile_chunks,
    embed_profile_chunks,
    evaluate_similarity,
    format_similar_examples,
    retrieve_similar_examples,
)
from app.filter.gemma_filter import evaluate_gemma_filter
from app.filter.gemini_scorer import score_job
from app.filter.hard_reject import is_hard_rejected
from app.filter.location_reject import is_location_rejected
from app.ingestion.google_ats import fetch_google_ats_jobs, fetch_serp_google_jobs
from app.ingestion.google_playwright import fetch_google_playwright_jobs
from app.ingestion.jobspy_source import fetch_jobspy_jobs
from app.ingestion.linkedin_auth import build_linkedin_client, enrich_description, polite_delay
from app.config import settings
from app.ingestion.normalizer import RawJob
from app.notify import notify_new_lead
from app.preferences import get_preferences

log = logging.getLogger(__name__)

_run_lock = False
_current_run_id: int | None = None


def is_pipeline_running() -> bool:
    return _run_lock


def get_current_run_id() -> int | None:
    return _current_run_id


def _log_reject(db: Session, run_id: int, job: RawJob, stage: RejectStage, reason: str, score=None, stack=None):
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


def _emit(phase: str, run_id: int, **kwargs) -> None:
    kwargs.setdefault("error_message", None)
    hub.emit(phase=phase, run_id=run_id, **kwargs)


def run_pipeline(db: Session, trigger: IngestionTrigger) -> IngestionRun:
    global _run_lock, _current_run_id
    if _run_lock:
        raise RuntimeError("Pipeline already running")

    profile = db.get(UserProfile, 1)
    if not profile or not profile.cv_text:
        raise ValueError("Upload your CV before syncing")

    prefs = get_preferences(db)
    _run_lock = True
    run = IngestionRun(
        trigger=trigger,
        started_at=datetime.utcnow(),
        status=IngestionStatus.running,
        raw_count=0,
        passed_count=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    _current_run_id = run.id
    _emit("scraping", run.id, raw_count=0, passed_count=0, processed=0, hard_rejected=0, deduped=0, llm_rejected=0, current_job=None)

    hard_rejected = deduped = llm_rejected = passed = processed = location_rejected = 0
    embedding_rejected = embedding_shadow_rejected = gemma_rejected = gemma_shadow_rejected = 0

    try:
        li_client = build_linkedin_client()
        email_blocklist = build_email_blocklist(db)
        profile_embeddings: list[list[float]] = []
        if settings.gemini_api_key and (
            settings.embedding_filter_enabled or settings.embedding_shadow_mode
        ):
            try:
                profile_embeddings = embed_profile_chunks(
                    build_profile_chunks(profile.cv_text or "", profile.profile_markdown or "")
                )
            except Exception as e:
                log.warning("[RAG Filter] Embedding setup failed open: %s", e)
        raw_jobs: list[RawJob] = []
        jobspy_jobs, site_counts = fetch_jobspy_jobs(prefs)
        playwright_jobs = fetch_google_playwright_jobs()
        serp_jobs = fetch_serp_google_jobs(prefs) if settings.serp_api_key else []
        ats_jobs = fetch_google_ats_jobs() if settings.serp_api_key else []
        raw_jobs.extend(jobspy_jobs)
        raw_jobs.extend(playwright_jobs)
        raw_jobs.extend(serp_jobs)
        raw_jobs.extend(ats_jobs)
        src_counts = {
            **site_counts,
            "google_playwright": len(playwright_jobs),
            "google_serp": len(serp_jobs),
            "google_ats": len(ats_jobs),
        }
        log.info("[Ingestion] Sources: %s", src_counts)
        _emit("scraping", run.id, raw_count=len(raw_jobs), sources=src_counts)

        if li_client:
            _emit("enriching", run.id, raw_count=len(raw_jobs))
            enriched = 0
            for job in raw_jobs:
                if job.platform_source != "linkedin":
                    continue
                if enriched >= settings.linkedin_enrich_max:
                    log.info("[LinkedIn] enrichment cap reached (%d)", settings.linkedin_enrich_max)
                    break
                extra = enrich_description(job.job_url, li_client)
                enriched += 1
                if extra:
                    job.description = extra
                polite_delay()

        run.raw_count = len(raw_jobs)
        db.commit()
        for job in raw_jobs:
            job.contact_email = sanitize_contact_email(job.contact_email, email_blocklist)
        _emit("filtering", run.id, raw_count=run.raw_count, sources=src_counts)

        dedupe_index = DedupeIndex(db)
        for job in raw_jobs:
            lead_created = False
            try:
                processed += 1
                label = f"{job.job_title} @ {job.company}"
                _emit("filtering", run.id, processed=processed, current_job=label,
                      hard_rejected=hard_rejected, deduped=deduped, llm_rejected=llm_rejected, passed_count=passed)

                rejected, reason = is_location_rejected(job.job_title, job.description, job.location, prefs)
                if rejected:
                    location_rejected += 1
                    _log_reject(db, run.id, job, RejectStage.location, reason or "")
                    continue

                rejected, reason = is_hard_rejected(job.job_title, job.description, prefs, job.company)
                if rejected:
                    hard_rejected += 1
                    _log_reject(db, run.id, job, RejectStage.hard_title, reason or "")
                    continue

                dup, dup_reason = dedupe_index.is_duplicate(job.job_url, job.company, job.job_title)
                if dup:
                    deduped += 1
                    _log_reject(db, run.id, job, RejectStage.dedupe, dup_reason or "")
                    continue

                dedupe_index.register_seen(job.job_url, job.company, job.job_title)

                if profile_embeddings and (settings.embedding_filter_enabled or settings.embedding_shadow_mode):
                    try:
                        similarity = evaluate_similarity(db, job, profile_embeddings)
                        if not similarity.passed:
                            if settings.embedding_filter_enabled and not settings.embedding_shadow_mode:
                                embedding_rejected += 1
                                llm_rejected += 1
                                _log_reject(
                                    db,
                                    run.id,
                                    job,
                                    RejectStage.embedding_filter,
                                    similarity.reason,
                                    round(similarity.score * 100),
                                )
                                dedupe_index.register_scored_reject(job.company, job.job_title)
                                continue
                            embedding_shadow_rejected += 1
                    except Exception as e:
                        log.warning("[RAG Filter] Embedding filter failed open for %s: %s", job.job_url, e)

                if settings.gemma_filter_enabled or settings.gemma_shadow_mode:
                    gemma_result = evaluate_gemma_filter(job, profile.cv_text, profile.profile_markdown or "")
                    if not gemma_result.passed:
                        if settings.gemma_filter_enabled and not settings.gemma_shadow_mode:
                            gemma_rejected += 1
                            llm_rejected += 1
                            _log_reject(db, run.id, job, RejectStage.gemma_filter, gemma_result.reason, 0)
                            dedupe_index.register_scored_reject(job.company, job.job_title)
                            continue
                        gemma_shadow_rejected += 1

                similar_examples = ""
                if settings.embedding_retrieve_examples > 0 and settings.gemini_api_key:
                    try:
                        similar_examples = format_similar_examples(retrieve_similar_examples(db, job))
                    except Exception as e:
                        log.warning("[RAG Filter] Similar-example retrieval failed open for %s: %s", job.job_url, e)

                try:
                    result = score_job(job, profile.cv_text, profile.profile_markdown or "", similar_examples, prefs)
                except Exception as e:
                    llm_rejected += 1
                    _log_reject(db, run.id, job, RejectStage.llm_score, str(e))
                    continue

                score = int(result.get("relevance_score", 0))
                stack = result.get("stack_match") or []
                eval_blob = result.get("match_evaluation") or {}
                reject_reason = result.get("match_reason", "Below threshold")
                if result.get("hard_reject_override"):
                    dbs = eval_blob.get("deal_breakers") or []
                    reject_reason = f"Deal breakers: {'; '.join(dbs)}" if dbs else reject_reason
                if score < prefs.score_threshold or result.get("hard_reject_override"):
                    llm_rejected += 1
                    _log_reject(db, run.id, job, RejectStage.llm_score, reject_reason, score, stack)
                    dedupe_index.register_scored_reject(job.company, job.job_title)
                    continue

                fp = job_fingerprint(job.company, job.job_title)
                if fp in dedupe_index.lead_fingerprints:
                    deduped += 1
                    _log_reject(db, run.id, job, RejectStage.dedupe, f"Duplicate role already in leads: {job.company} / {job.job_title}")
                    continue

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
                        ingestion_run_id=run.id,
                        created_at=datetime.utcnow(),
                    )
                )
                passed += 1
                lead_created = True
                dedupe_index.register_lead(job.job_url, job.company, job.job_title)
            finally:
                db.commit()
                if lead_created:
                    notify_new_lead(job.job_title, job.company, score, job.job_url)

        run.passed_count = passed
        run.status = IngestionStatus.completed
        run.finished_at = datetime.utcnow()
        db.commit()
        log.info("[Filter] Passed %s/%s leads", passed, run.raw_count)
        if location_rejected:
            log.info("[Filter] Location rejected %s jobs", location_rejected)
        if embedding_rejected or embedding_shadow_rejected or gemma_rejected or gemma_shadow_rejected:
            log.info(
                "[RAG Filter] embedding rejected=%s shadow=%s; gemma rejected=%s shadow=%s",
                embedding_rejected,
                embedding_shadow_rejected,
                gemma_rejected,
                gemma_shadow_rejected,
            )
        _emit("completed", run.id, raw_count=run.raw_count, passed_count=passed, processed=processed,
              hard_rejected=hard_rejected, deduped=deduped, llm_rejected=llm_rejected, current_job=None)
        return run
    except Exception as e:
        run.status = IngestionStatus.failed
        run.error_message = str(e)
        run.finished_at = datetime.utcnow()
        db.commit()
        _emit("failed", run.id, error_message=str(e), current_job=None)
        raise
    finally:
        _run_lock = False
        _current_run_id = None
