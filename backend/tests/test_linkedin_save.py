from datetime import date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.search as search_api
from app.api.search import router as search_router
from app.db.models import ApplicationStatus, Base, Lead, PlatformSource, RecruiterType, WorkplaceType
from app.db.session import get_db
from app.filter.dedupe import dedupe_leads
from app.ingestion.linkedin_search import attach_lead_status, save_linkedin_job
from app.schemas import LinkedinSearchItem

JOB_URL = "https://www.linkedin.com/jobs/view/4325555555/"


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


def _lead(
    *,
    job_url: str,
    title: str = "Data Engineer",
    company: str = "Acme",
    score: int | None = None,
    status: ApplicationStatus = ApplicationStatus.saved,
    created_at: datetime | None = None,
) -> Lead:
    return Lead(
        job_title=title,
        company=company,
        platform_source=PlatformSource.linkedin,
        submission_method="LinkedIn Easy Apply",
        recruiter_type=RecruiterType.direct,
        workplace_type=WorkplaceType.unknown,
        match_reason="Scored by pipeline",
        relevance_score=score,
        application_status=status,
        job_url=job_url,
        created_at=created_at or datetime.utcnow(),
    )


def _save(db, *, job_url=JOB_URL, status=ApplicationStatus.saved, title="Data Engineer", company="Acme"):
    return save_linkedin_job(
        db,
        job_title=title,
        company=company,
        job_url=job_url,
        date_posted=date(2026, 10, 9),
        status=status,
    )


def test_save_creates_unscored_lead(db):
    lead = _save(db)
    assert lead.id is not None
    assert lead.relevance_score is None
    assert lead.ingestion_run_id is None
    assert lead.application_status == ApplicationStatus.saved
    assert lead.platform_source == PlatformSource.linkedin
    assert lead.recruiter_type == RecruiterType.direct
    assert lead.match_reason == "Saved from LinkedIn search. Not scored."
    assert lead.date_posted == date(2026, 10, 9)


def test_saving_same_job_twice_reuses_the_lead(db):
    first = _save(db)
    second = _save(db)
    assert second.id == first.id
    assert len(db.scalars(select(Lead)).all()) == 1


def test_applied_is_not_downgraded_to_saved(db):
    _save(db, status=ApplicationStatus.applied)
    lead = _save(db, status=ApplicationStatus.saved)
    assert lead.application_status == ApplicationStatus.applied


def test_mark_applied_upgrades_saved_lead(db):
    _save(db)
    lead = _save(db, status=ApplicationStatus.applied)
    assert lead.application_status == ApplicationStatus.applied


def test_save_matches_scored_hidden_lead_on_another_url_and_keeps_score(db):
    db.add(_lead(job_url="https://www.linkedin.com/jobs/view/111", score=91, status=ApplicationStatus.hidden))
    db.commit()
    lead = _save(db, job_url="https://www.linkedin.com/jobs/view/222")
    assert len(db.scalars(select(Lead)).all()) == 1
    assert lead.relevance_score == 91
    assert lead.application_status == ApplicationStatus.saved


def test_trailing_slash_and_query_string_match_existing_lead(db):
    existing = _lead(job_url="https://www.linkedin.com/jobs/view/333", title="Platform Engineer", company="Other Co")
    db.add(existing)
    db.commit()
    lead = _save(db, job_url="https://www.linkedin.com/jobs/view/333/?trk=feed", title="Renamed", company="Elsewhere")
    assert lead.id == existing.id


def test_attach_lead_status_matches_by_url_or_role(db):
    db.add(_lead(job_url=JOB_URL, status=ApplicationStatus.applied))
    db.commit()
    items = [
        LinkedinSearchItem(job_title="Data Engineer", company="Acme", location=None, job_url=JOB_URL, date_posted=None),
        LinkedinSearchItem(
            job_title="Data Engineer", company="Acme", location=None,
            job_url="https://www.linkedin.com/jobs/view/999", date_posted=None,
        ),
        LinkedinSearchItem(
            job_title="Backend Engineer", company="Beta", location=None,
            job_url="https://www.linkedin.com/jobs/view/777", date_posted=None,
        ),
    ]
    statuses = [item.lead_status for item in attach_lead_status(db, items)]
    assert statuses == [ApplicationStatus.applied, ApplicationStatus.applied, None]


def test_dedupe_prefers_scored_lead_over_newer_unscored_duplicate():
    older_scored = _lead(job_url="https://www.linkedin.com/jobs/view/1", score=80, created_at=datetime(2026, 10, 1))
    newer_unscored = _lead(job_url="https://www.linkedin.com/jobs/view/2", created_at=datetime(2026, 10, 9))
    assert dedupe_leads([newer_unscored, older_scored]) == [older_scored]
    assert dedupe_leads([older_scored, newer_unscored]) == [older_scored]


def test_dedupe_keeps_newest_unscored_duplicate():
    older = _lead(job_url="https://www.linkedin.com/jobs/view/1", created_at=datetime(2026, 10, 1))
    newer = _lead(job_url="https://www.linkedin.com/jobs/view/2", created_at=datetime(2026, 10, 9))
    assert dedupe_leads([older, newer]) == [newer]


def test_save_endpoint_returns_lead_id_and_status(client):
    res = client.post(
        "/api/search/linkedin/save",
        json={
            "job_title": "Data Engineer",
            "company": "Acme",
            "job_url": JOB_URL,
            "date_posted": "2026-10-09",
            "status": "applied",
        },
    )
    assert res.status_code == 200
    assert res.json()["application_status"] == "applied"
    assert isinstance(res.json()["lead_id"], int)


def test_save_endpoint_rejects_hidden_status(client):
    res = client.post(
        "/api/search/linkedin/save",
        json={"job_title": "Data Engineer", "company": "Acme", "job_url": JOB_URL, "status": "hidden"},
    )
    assert res.status_code == 422


def test_search_endpoint_reports_lead_status(client, db, monkeypatch):
    db.add(_lead(job_url=JOB_URL, status=ApplicationStatus.saved))
    db.commit()
    monkeypatch.setattr(
        search_api,
        "search_linkedin_jobs",
        lambda term, place, hours, limit: [
            LinkedinSearchItem(job_title="Data Engineer", company="Acme", location=None, job_url=JOB_URL, date_posted=None)
        ],
    )
    res = client.get("/api/search/linkedin", params={"q": "data engineer"})
    assert res.status_code == 200
    assert res.json()["items"][0]["lead_status"] == "saved"
