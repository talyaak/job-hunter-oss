from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.search import router as search_router
from app.db.models import ApplicationStatus, Base
from app.db.session import get_db
from app.ingestion.linkedin_search import save_linkedin_job

URL_A = "https://www.linkedin.com/jobs/view/1001"
URL_B = "https://www.linkedin.com/jobs/view/1002"
URL_C = "https://www.linkedin.com/jobs/view/1003"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(search_router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _search(term="data engineer", location="Tel Aviv, Israel", hours=168, urls=(URL_A,)):
    return {
        "query": term,
        "location": location,
        "hours": hours,
        "total": len(urls),
        "items": [
            {
                "job_title": "Data Engineer",
                "company": "Acme",
                "location": None,
                "job_url": url,
                "date_posted": "2026-10-09",
                "lead_status": None,
            }
            for url in urls
        ],
    }


def _post(client, **kwargs):
    res = client.post("/api/search/linkedin/history", json=_search(**kwargs))
    assert res.status_code == 200
    return res.json()


def test_history_starts_empty(client):
    assert client.get("/api/search/linkedin/history").json() == []


def test_post_stores_entry_with_utc_timestamp(client):
    entries = _post(client)
    assert len(entries) == 1
    assert entries[0]["term"] == "data engineer"
    assert entries[0]["new_urls"] is None
    assert entries[0]["fetched_at"].endswith("Z")
    assert entries[0]["response"]["items"][0]["job_url"] == URL_A


def test_same_search_ignoring_case_replaces_entry(client):
    _post(client, term="Data Engineer")
    _post(client, term="Backend Engineer")
    entries = _post(client, term="data engineer")
    assert [e["term"] for e in entries] == ["data engineer", "Backend Engineer"]


def test_hours_distinguish_searches(client):
    _post(client, hours=24)
    entries = _post(client, hours=168)
    assert len(entries) == 2


def test_repeat_search_reports_only_unseen_jobs_as_new(client):
    _post(client, urls=(URL_A, URL_B))
    entries = _post(client, urls=(URL_B, URL_C))
    assert len(entries) == 1
    assert entries[0]["new_urls"] == [URL_C]


def test_history_keeps_ten_newest(client):
    for i in range(11):
        entries = _post(client, term=f"search {i}")
    assert len(entries) == 10
    assert entries[0]["term"] == "search 10"
    assert all(e["term"] != "search 0" for e in entries)


def test_lead_status_is_refreshed_when_history_is_read(client, db):
    _post(client)
    save_linkedin_job(
        db,
        job_title="Data Engineer",
        company="Acme",
        job_url=URL_A,
        date_posted=date(2026, 10, 9),
        status=ApplicationStatus.applied,
    )
    entries = client.get("/api/search/linkedin/history").json()
    assert entries[0]["response"]["items"][0]["lead_status"] == "applied"


def test_clear_removes_all_entries(client):
    _post(client)
    _post(client, term="backend engineer")
    assert client.delete("/api/search/linkedin/history").status_code == 204
    assert client.get("/api/search/linkedin/history").json() == []


def test_filters_default_when_never_saved(client):
    body = client.get("/api/search/linkedin/filters").json()
    assert body == {"ignore_text": "", "removed_keys": [], "updated_at": None}


def test_put_filters_round_trips_with_utc_timestamp(client):
    payload = {"ignore_text": "GTM, Staff", "removed_keys": ["1001", URL_A]}
    res = client.put("/api/search/linkedin/filters", json=payload)
    assert res.status_code == 200
    assert res.json()["ignore_text"] == "GTM, Staff"
    assert res.json()["removed_keys"] == ["1001", URL_A]
    assert res.json()["updated_at"].endswith("Z")
    assert client.get("/api/search/linkedin/filters").json() == res.json()


def test_put_filters_replaces_previous_state(client):
    client.put("/api/search/linkedin/filters", json={"ignore_text": "GTM", "removed_keys": ["1001"]})
    client.put("/api/search/linkedin/filters", json={})
    body = client.get("/api/search/linkedin/filters").json()
    assert body["ignore_text"] == ""
    assert body["removed_keys"] == []
    assert body["updated_at"] is not None


def test_put_filters_rejects_oversized_ignore_text(client):
    res = client.put("/api/search/linkedin/filters", json={"ignore_text": "x" * 2001, "removed_keys": []})
    assert res.status_code == 422
