import httpx
import jobspy
import pandas as pd

from app.ingestion import linkedin_search
from app.ingestion.linkedin_search import fetch_posted_ago, search_linkedin_jobs

JOB_URL = "https://www.linkedin.com/jobs/view/4325555555/"
GUEST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4325555555"
HOUR_HTML = '<span class="posted-time-ago__text topcard__flavor--metadata">\n  21 hours ago\n</span>'


def test_results_sorted_newest_first_with_undated_last(monkeypatch):
    df = pd.DataFrame(
        [
            {"title": "Old", "company": "A", "location": "Tel Aviv", "job_url": "u1", "date_posted": "2026-10-01"},
            {"title": "Undated", "company": "B", "location": None, "job_url": "u2", "date_posted": None},
            {"title": "New", "company": "C", "location": "Herzliya", "job_url": "u3", "date_posted": "2026-10-09"},
        ]
    )
    captured = {}

    def fake_scrape(**kwargs):
        captured.update(kwargs)
        return df

    monkeypatch.setattr(jobspy, "scrape_jobs", fake_scrape)
    items = search_linkedin_jobs("python developer", "Tel Aviv, Israel", 168, 50)

    assert [i.job_title for i in items] == ["New", "Old", "Undated"]
    assert items[2].location is None
    assert captured["search_term"] == "python developer"
    assert captured["site_name"] == ["linkedin"]
    assert captured["linkedin_fetch_description"] is False


def test_empty_result_set(monkeypatch):
    monkeypatch.setattr(jobspy, "scrape_jobs", lambda **kwargs: pd.DataFrame())
    assert search_linkedin_jobs("nothing matches", "Tel Aviv, Israel", 24, 10) == []


def test_search_does_not_fetch_job_pages(monkeypatch):
    df = pd.DataFrame(
        [{"title": "New", "company": "A", "location": None, "job_url": JOB_URL, "date_posted": "2026-10-09"}]
    )
    monkeypatch.setattr(jobspy, "scrape_jobs", lambda **kwargs: df)

    def fail(*args, **kwargs):
        raise AssertionError("search must not fetch job pages")

    monkeypatch.setattr(linkedin_search, "fetch_posted_ago", fail)
    assert len(search_linkedin_jobs("python developer", "Tel Aviv, Israel", 24, 10)) == 1


def test_fetch_posted_ago_reads_hour_label_from_job_page():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, text=HOUR_HTML)

    assert fetch_posted_ago(JOB_URL, httpx.MockTransport(handler)) == "21 hours ago"
    assert seen == [GUEST_URL]


def test_fetch_posted_ago_retries_after_rate_limit(monkeypatch):
    monkeypatch.setattr(linkedin_search, "RETRY_WAITS", (0.0,))
    responses = iter([httpx.Response(429), httpx.Response(200, text=HOUR_HTML)])
    assert fetch_posted_ago(JOB_URL, httpx.MockTransport(lambda req: next(responses))) == "21 hours ago"


def test_fetch_posted_ago_gives_up_after_repeated_rate_limit(monkeypatch):
    monkeypatch.setattr(linkedin_search, "RETRY_WAITS", (0.0, 0.0))
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429)

    assert fetch_posted_ago(JOB_URL, httpx.MockTransport(handler)) is None
    assert len(calls) == 3


def test_fetch_posted_ago_never_requests_urls_without_a_job_id():
    def handler(request):
        raise AssertionError("no request expected")

    assert fetch_posted_ago("https://example.com/not-a-job", httpx.MockTransport(handler)) is None
