import logging
import re
from datetime import date, timedelta
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.ingestion.jobspy_source import google_term
from app.preferences import Preferences, get_preferences
from app.ingestion.normalizer import normalize_job

log = logging.getLogger(__name__)

ATS_SITES = "(site:boards.greenhouse.io OR site:comeet.com OR site:jobs.lever.co OR site:workday.com)"


def boolean_query(prefs: Preferences | None = None) -> str:
    """ATS-board search built from the user's target titles and location."""
    prefs = prefs or get_preferences()
    parts = [ATS_SITES, prefs.search_term()]
    if prefs.search_location:
        parts.append(f'"{prefs.search_location}"')
    parts.append('-"Jobs at" -"Careers at"')
    return " ".join(parts)

ATS_PATTERN = re.compile(
    r"https?://(?:[\w.-]+\.)?(?:greenhouse\.io|comeet\.com|jobs\.lever\.co|workday\.com)[^\s\"'<>]*",
    re.I,
)


def _parse_posted_at(val: str | None) -> date | None:
    if not val:
        return None
    v = val.lower()
    if "hour" in v or "today" in v or "just" in v:
        return date.today()
    m = re.search(r"(\d+)\s+day", v)
    if m:
        return date.today() - timedelta(days=int(m.group(1)))
    if "week" in v:
        m = re.search(r"(\d+)", v)
        days = int(m.group(1)) * 7 if m else 7
        return date.today() - timedelta(days=days)
    return None


def fetch_serp_google_jobs(prefs: Preferences | None = None) -> list:
    prefs = prefs or get_preferences()
    from app.ingestion.normalizer import RawJob

    if not settings.serp_api_key:
        return []

    jobs: list[RawJob] = []
    wanted = settings.ingestion_pool_size * settings.ingestion_pool_count
    token: str | None = None
    while len(jobs) < wanted:
        params: dict = {
            "engine": "google_jobs",
            "q": google_term(prefs),
            "location": prefs.search_location,
            "hl": "en",
            "api_key": settings.serp_api_key,
        }
        if token:
            params["next_page_token"] = token
        try:
            resp = httpx.get("https://serpapi.com/search", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.info("[Ingestion] google (SerpAPI): failed: %s", e)
            break

        batch = data.get("jobs_results") or []
        if not batch:
            break
        for item in batch:
            apply = item.get("apply_options") or []
            job_url = apply[0].get("link") if apply else item.get("share_link", "")
            if not job_url:
                continue
            ext = item.get("detected_extensions") or {}
            jobs.append(
                normalize_job(
                    job_title=str(item.get("title", "")),
                    company=str(item.get("company_name", "")),
                    job_url=job_url,
                    description=str(item.get("description", "")),
                    platform_source="google",
                    date_posted=_parse_posted_at(ext.get("posted_at")),
                )
            )
            if len(jobs) >= wanted:
                break

        token = (data.get("serpapi_pagination") or {}).get("next_page_token")
        if not token:
            break

    log.info("[Ingestion] google (SerpAPI): %d jobs", len(jobs))
    return jobs


def _serp_urls() -> list[str]:
    if settings.serp_api_key:
        resp = httpx.get(
            "https://serpapi.com/search",
            params={"q": boolean_query(), "api_key": settings.serp_api_key, "num": 10},
            timeout=30,
        )
        resp.raise_for_status()
        urls = []
        for item in resp.json().get("organic_results", []):
            link = item.get("link", "")
            if ATS_PATTERN.search(link):
                urls.append(link)
        return urls[: settings.google_ats_max_pages * 10]

    try:
        from googlesearch import search
    except ImportError:
        return []

    urls: list[str] = []
    for page in range(settings.google_ats_max_pages):
        start = page * 10
        for u in search(boolean_query(), num_results=10, sleep_interval=2, advanced=True):
            if isinstance(u, str):
                link = u
            else:
                link = getattr(u, "url", str(u))
            if ATS_PATTERN.search(link):
                urls.append(link)
        if len(urls) >= (page + 1) * 5:
            break
    return list(dict.fromkeys(urls))


def _fetch_page(url: str) -> tuple[str, str]:
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True)
        r.raise_for_status()
        text = r.text
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", text, re.I)
        title = title_m.group(1).strip() if title_m else urlparse(url).path
        body = re.sub(r"<[^>]+>", " ", text)
        body = re.sub(r"\s+", " ", body)[:8000]
        return title, body
    except Exception:
        return urlparse(url).path, ""


def fetch_google_ats_jobs() -> list:
    from app.ingestion.normalizer import RawJob

    jobs: list[RawJob] = []
    urls = _serp_urls()
    if not urls and not settings.serp_api_key and not settings.google_playwright_enabled:
        log.info(
            "[Ingestion] google_ats: 0 — SerpAPI key not set; use Playwright Google scraper instead"
        )
    for url in urls:
        title, desc = _fetch_page(url)
        host = urlparse(url).netloc
        company = host.split(".")[0].title()
        jobs.append(
            normalize_job(
                job_title=title[:500],
                company=company,
                job_url=url,
                description=desc,
                platform_source="google",
            )
        )
    log.info("[Ingestion] google_ats: %d jobs", len(jobs))
    return jobs
