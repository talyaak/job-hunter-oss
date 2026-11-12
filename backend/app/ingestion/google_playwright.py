import logging
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import settings
from app.ingestion.google_ats import _fetch_page, boolean_query
from app.ingestion.normalizer import RawJob, normalize_job

log = logging.getLogger(__name__)

STEALTH_ARGS = ["--disable-blink-features=AutomationControlled"]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
JOB_HOST_RE = re.compile(
    r"greenhouse\.io|comeet\.com|jobs\.lever\.co|workday\.com|ashbyhq\.com|"
    r"myworkdayjobs\.com|teamtailor\.com|breezy\.hr",
    re.I,
)
SKIP_HOST_RE = re.compile(r"linkedin\.com|indeed\.com|glassdoor\.com|google\.com", re.I)


@dataclass
class SearchLink:
    url: str
    title: str


@contextmanager
def _playwright_page():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=settings.google_playwright_headless,
            args=STEALTH_ARGS,
        )
        ctx = browser.new_context(
            locale="en-US",
            viewport={"width": 1280, "height": 900},
            user_agent=USER_AGENT,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        ctx.add_init_script(
            'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        )
        page = ctx.new_page()
        try:
            page.goto("https://www.google.com/ncr", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(800)
            yield page
        finally:
            browser.close()


def _organic_links(page) -> list[SearchLink]:
    raw = page.eval_on_selector_all(
        "a:has(h3)",
        'els => els.map(e => ({href: e.href.split("#")[0], title: (e.querySelector("h3")||{}).innerText||""}))',
    )
    links: list[SearchLink] = []
    for item in raw:
        href = (item.get("href") or "").strip()
        title = (item.get("title") or "").strip()
        if href.startswith("http") and title and not SKIP_HOST_RE.search(href):
            links.append(SearchLink(url=href, title=title))
    return links


def _run_search(page, query: str) -> None:
    page.goto("https://www.google.com/search", wait_until="domcontentloaded", timeout=30000)
    page.locator('textarea[name="q"], input[name="q"]').first.fill(query)
    page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle", timeout=60000)
    page.wait_for_timeout(1500)


def _advance_pages(page, count: int) -> int:
    advanced = 0
    for _ in range(count):
        next_btn = page.locator('a#pnnext, a[aria-label="Next page"]').first
        if not next_btn.count():
            break
        next_btn.click()
        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(1200)
        advanced += 1
    return advanced


def collect_google_links(
    query: str,
    max_results: int,
    max_pages: int,
    page_offset: int = 0,
) -> tuple[list[SearchLink], int]:
    if not settings.google_playwright_enabled:
        return [], 0

    seen: set[str] = set()
    collected: list[SearchLink] = []
    pages_used = 0

    try:
        with _playwright_page() as page:
            _run_search(page, query)
            _advance_pages(page, page_offset)

            for _ in range(max_pages):
                pages_used += 1
                for link in _organic_links(page):
                    if link.url in seen or not JOB_HOST_RE.search(link.url):
                        continue
                    seen.add(link.url)
                    collected.append(link)
                    if len(collected) >= max_results:
                        return collected, page_offset + pages_used

                if not _advance_pages(page, 1):
                    break
    except Exception as e:
        log.info("[Ingestion] google (Playwright): search failed: %s", e)

    return collected, page_offset + pages_used


def _company_from_url(url: str, title: str) -> str:
    if " at " in title:
        part = title.rsplit(" at ", 1)[-1]
        part = re.sub(r"\s*-\s*(Comeet|Greenhouse|Lever).*$", "", part, flags=re.I)
        if part.strip():
            return part.strip()[:120]
    host = urlparse(url).netloc.lower()
    m = re.search(r"/jobs/([^/]+)/", url)
    if m:
        return m.group(1).replace("-", " ").title()
    parts = host.split(".")
    return parts[-2].title() if len(parts) >= 2 else host


def links_to_jobs(links: list[SearchLink]) -> list[RawJob]:
    jobs: list[RawJob] = []
    for link in links:
        _, desc = _fetch_page(link.url)
        jobs.append(
            normalize_job(
                job_title=link.title[:500],
                company=_company_from_url(link.url, link.title),
                job_url=link.url,
                description=desc,
                platform_source="google",
            )
        )
    return jobs


def fetch_google_playwright_jobs() -> list[RawJob]:
    if not settings.google_playwright_enabled:
        log.info("[Ingestion] google (Playwright): disabled")
        return []

    all_links: list[SearchLink] = []
    seen_urls: set[str] = set()
    page_offset = 0

    for pool in range(settings.ingestion_pool_count):
        if pool > 0:
            log.info("[Ingestion] google (Playwright) dry-off %ds", settings.ingestion_pool_dryoff_seconds)
            time.sleep(settings.ingestion_pool_dryoff_seconds)

        pool_links, page_offset = collect_google_links(
            query=boolean_query(),
            max_results=settings.ingestion_pool_size,
            max_pages=settings.google_pool_pages,
            page_offset=page_offset,
        )
        added = 0
        for link in pool_links:
            if link.url in seen_urls:
                continue
            seen_urls.add(link.url)
            all_links.append(link)
            added += 1
        log.info("[Ingestion] google (Playwright) pool %d: %d links", pool + 1, added)

    jobs = links_to_jobs(all_links)
    log.info("[Ingestion] google (Playwright): %d links → %d jobs", len(all_links), len(jobs))
    return jobs
