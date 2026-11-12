import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import ApplicationStatus, LinkedinSearchFilters, LinkedinSearchHistory
from app.db.session import get_db
from app.ingestion.linkedin_search import (
    attach_lead_status,
    fetch_posted_ago,
    save_linkedin_job,
    search_linkedin_jobs,
)
from app.preferences import get_preferences
from app.schemas import (
    LinkedinPostedAgoOut,
    LinkedinSaveIn,
    LinkedinSaveOut,
    LinkedinSearchFiltersIn,
    LinkedinSearchFiltersOut,
    LinkedinSearchHistoryOut,
    LinkedinSearchOut,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/linkedin", response_model=LinkedinSearchOut)
def search_linkedin(
    q: str = Query(..., max_length=120),
    location: str = Query("", max_length=120),
    hours: int = Query(168, ge=1, le=720),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    term = q.strip()
    place = location.strip() or get_preferences(db).search_location
    if len(term) < 2:
        raise HTTPException(400, "Enter at least 2 characters.")
    try:
        items = search_linkedin_jobs(term, place, hours, limit)
    except Exception as e:
        log.warning("[Search] LinkedIn search failed for %r: %s", term, e)
        raise HTTPException(502, "LinkedIn search failed. Try again in a minute.") from e
    items = attach_lead_status(db, items)
    return LinkedinSearchOut(query=term, location=place, hours=hours, total=len(items), items=items)


@router.post("/linkedin/save", response_model=LinkedinSaveOut)
def save_linkedin_search_job(body: LinkedinSaveIn, db: Session = Depends(get_db)):
    lead = save_linkedin_job(
        db,
        job_title=body.job_title,
        company=body.company,
        job_url=body.job_url,
        date_posted=body.date_posted,
        status=ApplicationStatus(body.status),
    )
    return LinkedinSaveOut(lead_id=lead.id, application_status=lead.application_status)


@router.get("/linkedin/posted-ago", response_model=LinkedinPostedAgoOut)
def linkedin_posted_ago(job_url: str = Query(..., max_length=500)):
    return LinkedinPostedAgoOut(posted_ago=fetch_posted_ago(job_url))


HISTORY_LIMIT = 10


def _search_key(term: str, location: str, hours: int) -> tuple[str, str, int]:
    return term.strip().lower(), location.strip().lower(), hours


def _newest_first():
    return select(LinkedinSearchHistory).order_by(
        LinkedinSearchHistory.fetched_at.desc(), LinkedinSearchHistory.id.desc()
    )


def _history_out(db: Session) -> list[LinkedinSearchHistoryOut]:
    rows = db.scalars(_newest_first()).all()
    responses = [LinkedinSearchOut.model_validate_json(row.response_json) for row in rows]
    refreshed = attach_lead_status(db, [item for response in responses for item in response.items])
    out: list[LinkedinSearchHistoryOut] = []
    start = 0
    for row, response in zip(rows, responses):
        end = start + len(response.items)
        out.append(
            LinkedinSearchHistoryOut(
                term=row.term,
                location=row.location,
                hours=row.hours,
                fetched_at=row.fetched_at.replace(tzinfo=timezone.utc),
                new_urls=json.loads(row.new_urls_json) if row.new_urls_json is not None else None,
                response=response.model_copy(update={"items": refreshed[start:end]}),
            )
        )
        start = end
    return out


@router.get("/linkedin/history", response_model=list[LinkedinSearchHistoryOut])
def list_linkedin_search_history(db: Session = Depends(get_db)):
    return _history_out(db)


@router.post("/linkedin/history", response_model=list[LinkedinSearchHistoryOut])
def save_linkedin_search_history(body: LinkedinSearchOut, db: Session = Depends(get_db)):
    key = _search_key(body.query, body.location, body.hours)
    rows = db.scalars(select(LinkedinSearchHistory)).all()
    previous = next((row for row in rows if _search_key(row.term, row.location, row.hours) == key), None)
    new_urls = None
    if previous is not None:
        seen = {item.job_url for item in LinkedinSearchOut.model_validate_json(previous.response_json).items}
        new_urls = [item.job_url for item in body.items if item.job_url not in seen]
        db.delete(previous)
    db.add(
        LinkedinSearchHistory(
            term=body.query,
            location=body.location,
            hours=body.hours,
            fetched_at=datetime.utcnow(),
            response_json=body.model_dump_json(),
            new_urls_json=json.dumps(new_urls) if new_urls is not None else None,
        )
    )
    db.flush()
    for row in db.scalars(_newest_first().offset(HISTORY_LIMIT)).all():
        db.delete(row)
    db.commit()
    return _history_out(db)


@router.delete("/linkedin/history", status_code=204)
def clear_linkedin_search_history(db: Session = Depends(get_db)):
    db.execute(delete(LinkedinSearchHistory))
    db.commit()


FILTERS_ID = 1


def _filters_out(row: LinkedinSearchFilters | None) -> LinkedinSearchFiltersOut:
    if row is None:
        return LinkedinSearchFiltersOut(ignore_text="", removed_keys=[], updated_at=None)
    return LinkedinSearchFiltersOut(
        ignore_text=row.ignore_text,
        removed_keys=json.loads(row.removed_keys_json),
        updated_at=row.updated_at.replace(tzinfo=timezone.utc),
    )


@router.get("/linkedin/filters", response_model=LinkedinSearchFiltersOut)
def get_linkedin_filters(db: Session = Depends(get_db)):
    return _filters_out(db.get(LinkedinSearchFilters, FILTERS_ID))


@router.put("/linkedin/filters", response_model=LinkedinSearchFiltersOut)
def put_linkedin_filters(body: LinkedinSearchFiltersIn, db: Session = Depends(get_db)):
    row = db.get(LinkedinSearchFilters, FILTERS_ID)
    if row is None:
        row = LinkedinSearchFilters(id=FILTERS_ID)
        db.add(row)
    row.ignore_text = body.ignore_text
    row.removed_keys_json = json.dumps(body.removed_keys)
    row.updated_at = datetime.utcnow()
    db.commit()
    return _filters_out(row)
