import logging
import time
from datetime import date

import pandas as pd

from app.config import settings
from app.ingestion.normalizer import RawJob, normalize_job
from app.preferences import Preferences, get_preferences

log = logging.getLogger(__name__)


def search_term(prefs: Preferences | None = None) -> str:
    return (prefs or get_preferences()).search_term()


def google_term(prefs: Preferences | None = None) -> str:
    prefs = prefs or get_preferences()
    return f"{prefs.search_term()} jobs {prefs.search_location}".strip()


def _parse_date(val) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, date):
        return val
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


def _scrape_site(site: str, results_wanted: int, prefs: Preferences, offset: int = 0) -> pd.DataFrame | None:
    from jobspy import scrape_jobs

    kwargs: dict = dict(
        site_name=[site],
        location=prefs.search_location,
        results_wanted=results_wanted,
        offset=offset,
        hours_old=prefs.hours_old or settings.jobspy_hours_old,
        description_format="markdown",
        verbose=0,
    )
    kwargs["search_term"] = prefs.search_term()
    if site == "indeed" and prefs.country:
        kwargs["country_indeed"] = prefs.country
    if site == "linkedin":
        kwargs["linkedin_fetch_description"] = True
    try:
        return scrape_jobs(**kwargs)
    except Exception as e:
        log.info("[Ingestion] %s failed: %s", site, e)
        return None


def _df_to_jobs(df: pd.DataFrame) -> list[RawJob]:
    jobs: list[RawJob] = []
    for _, row in df.iterrows():
        platform = str(row.get("site", "indeed")).lower()
        emails = row.get("emails")
        email = str(emails).split(",")[0].strip() if emails and str(emails) != "nan" else None
        remote = row.get("is_remote")
        hint = "remote" if remote is True else None
        desc = row.get("description")
        loc = row.get("location")
        location = None if loc is None or str(loc) == "nan" else str(loc)
        jobs.append(
            normalize_job(
                job_title=str(row.get("title", "")),
                company=str(row.get("company", "")),
                job_url=str(row.get("job_url", "")),
                description="" if desc is None or str(desc) == "nan" else str(desc),
                platform_source=platform,
                date_posted=_parse_date(row.get("date_posted")),
                location=location,
                workplace_type_hint=hint,
                contact_email=email,
            )
        )
    return jobs


def fetch_jobspy_jobs(prefs: Preferences | None = None) -> tuple[list[RawJob], dict[str, int]]:
    prefs = prefs or get_preferences()
    frames: list[pd.DataFrame] = []
    site_counts: dict[str, int] = {}

    df_indeed = _scrape_site("indeed", settings.indeed_results_wanted, prefs)
    indeed_count = 0 if df_indeed is None or df_indeed.empty else len(df_indeed)
    site_counts["indeed"] = indeed_count
    log.info("[Ingestion] indeed: %d jobs", indeed_count)
    if df_indeed is not None and not df_indeed.empty:
        frames.append(df_indeed)

    linkedin_total = 0
    for pool in range(settings.ingestion_pool_count if settings.linkedin_enabled else 0):
        if pool > 0:
            log.info("[Ingestion] linkedin dry-off %ds", settings.ingestion_pool_dryoff_seconds)
            time.sleep(settings.ingestion_pool_dryoff_seconds)
        offset = pool * settings.ingestion_pool_size
        df_li = _scrape_site("linkedin", settings.ingestion_pool_size, prefs, offset=offset)
        count = 0 if df_li is None or df_li.empty else len(df_li)
        linkedin_total += count
        log.info("[Ingestion] linkedin pool %d: %d jobs", pool + 1, count)
        if df_li is not None and not df_li.empty:
            frames.append(df_li)
    site_counts["linkedin"] = linkedin_total

    if not frames:
        return [], site_counts

    return _df_to_jobs(pd.concat(frames, ignore_index=True)), site_counts
