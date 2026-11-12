from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlparse

ATS_HOSTS = ("greenhouse.io", "lever.co", "comeet.com", "workday.com")


@dataclass
class RawJob:
    job_title: str
    company: str
    job_url: str
    description: str
    platform_source: str
    date_posted: date | None = None
    location: str | None = None
    workplace_type_hint: str | None = None
    contact_email: str | None = None
    submission_method: str = "Unknown"


def infer_submission_method(platform_source: str, job_url: str, description: str = "") -> str:
    host = urlparse(job_url).netloc.lower()
    desc = description.lower()

    if platform_source == "linkedin":
        if "linkedin.com" in host and ("/jobs/view/" in job_url or "easy apply" in desc):
            return "LinkedIn Easy Apply"
    if platform_source == "glassdoor":
        if "glassdoor.com" in host:
            return "Glassdoor Fast Apply"
    if platform_source == "indeed":
        if "indeed.com" in host:
            return "Indeed Apply"
    if any(h in host for h in ATS_HOSTS) or (platform_source == "google"):
        return "Company Website"
    return "Unknown"


def normalize_job(
    job_title: str,
    company: str,
    job_url: str,
    description: str,
    platform_source: str,
    date_posted: date | None = None,
    location: str | None = None,
    workplace_type_hint: str | None = None,
    contact_email: str | None = None,
) -> RawJob:
    method = infer_submission_method(platform_source, job_url, description)
    return RawJob(
        job_title=job_title,
        company=company,
        job_url=job_url,
        description=description or "",
        platform_source=platform_source,
        date_posted=date_posted,
        location=location,
        workplace_type_hint=workplace_type_hint,
        contact_email=contact_email,
        submission_method=method,
    )
