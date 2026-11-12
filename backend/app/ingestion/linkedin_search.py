import re
import time
from datetime import date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApplicationStatus, Lead, PlatformSource, RecruiterType, WorkplaceType
from app.filter.dedupe import LeadIndex
from app.ingestion.jobspy_source import _parse_date
from app.ingestion.normalizer import infer_submission_method
from app.schemas import LinkedinSearchItem

GUEST_JOB_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
JOB_ID_RE = re.compile(r"/jobs/view/(\d+)")
POSTED_AGO_RE = re.compile(r"posted-time-ago__text[^>]*>\s*([^<]+?)\s*<")
RETRY_WAITS = (2.0, 4.0)


def search_linkedin_jobs(term: str, location: str, hours: int, limit: int) -> list[LinkedinSearchItem]:
    from jobspy import scrape_jobs

    df = scrape_jobs(
        site_name=["linkedin"],
        search_term=term,
        location=location,
        results_wanted=limit,
        hours_old=hours,
        linkedin_fetch_description=False,
        verbose=0,
    )
    items: list[LinkedinSearchItem] = []
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            loc = row.get("location")
            items.append(
                LinkedinSearchItem(
                    job_title=str(row.get("title", "")),
                    company=str(row.get("company", "")),
                    location=None if loc is None or str(loc) == "nan" else str(loc),
                    job_url=str(row.get("job_url", "")),
                    date_posted=_parse_date(row.get("date_posted")),
                )
            )
    items.sort(key=lambda item: item.date_posted or date.min, reverse=True)
    return items[:limit]


# List pages carry only the date; the job page carries the relative hour.
def fetch_posted_ago(job_url: str, transport: httpx.BaseTransport | None = None) -> str | None:
    job = JOB_ID_RE.search(job_url)
    if not job:
        return None
    url = GUEST_JOB_URL.format(job_id=job.group(1))
    waits = iter(RETRY_WAITS)
    with httpx.Client(headers=HEADERS, timeout=10, transport=transport) as client:
        while True:
            try:
                resp = client.get(url)
            except httpx.HTTPError:
                return None
            if resp.status_code == 200:
                found = POSTED_AGO_RE.search(resp.text)
                return found.group(1) if found else None
            wait = next(waits, None)
            if resp.status_code != 429 or wait is None:
                return None
            time.sleep(wait)


def attach_lead_status(db: Session, items: list[LinkedinSearchItem]) -> list[LinkedinSearchItem]:
    index = LeadIndex(db.scalars(select(Lead)).all())
    out = []
    for item in items:
        lead = index.find(item.job_url, item.company, item.job_title)
        out.append(item.model_copy(update={"lead_status": lead.application_status if lead else None}))
    return out


def save_linkedin_job(
    db: Session,
    *,
    job_title: str,
    company: str,
    job_url: str,
    date_posted: date | None,
    status: ApplicationStatus,
) -> Lead:
    existing = LeadIndex(db.scalars(select(Lead)).all()).find(job_url, company, job_title)
    if existing:
        if not (existing.application_status == ApplicationStatus.applied and status == ApplicationStatus.saved):
            existing.application_status = status
            db.commit()
        return existing

    lead = Lead(
        date_posted=date_posted,
        job_title=job_title,
        company=company,
        platform_source=PlatformSource.linkedin,
        submission_method=infer_submission_method("linkedin", job_url),
        recruiter_type=RecruiterType.direct,
        workplace_type=WorkplaceType.unknown,
        match_reason="Saved from LinkedIn search. Not scored.",
        relevance_score=None,
        application_status=status,
        job_url=job_url,
        ingestion_run_id=None,
        created_at=datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
