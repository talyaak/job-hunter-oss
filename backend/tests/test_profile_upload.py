import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import profile as profile_api
from app.db.models import Base, UserProfile
from app.db.session import get_db
from app.main import app

OLD_TEXT = "Senior developer with eight years of TypeScript and Python. " * 10
NEW_TEXT = "Backend engineer working with Go and Kubernetes in production. " * 10


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as s:
        s.add(UserProfile(id=1, cv_text=OLD_TEXT, cv_filename="old.pdf", profile_markdown=OLD_TEXT))
        s.commit()

    def override_db():
        with session_factory() as s:
            yield s

    monkeypatch.setattr(profile_api, "RESUME_PATH", tmp_path / "resume.pdf")
    app.dependency_overrides[get_db] = override_db
    yield TestClient(app), session_factory, tmp_path
    app.dependency_overrides.clear()


def test_scanned_cv_is_rejected_and_previous_cv_kept(client, monkeypatch):
    api, session_factory, tmp_path = client
    monkeypatch.setattr(profile_api, "extract_pdf_text", lambda data: "")

    resp = api.post("/api/profile", files={"cv": ("scan.pdf", b"%PDF-scan", "application/pdf")})

    assert resp.status_code == 400
    assert "Your previous data was kept" in resp.json()["detail"]
    with session_factory() as s:
        row = s.get(UserProfile, 1)
        assert row.cv_filename == "old.pdf"
        assert row.cv_text == OLD_TEXT
    assert not (tmp_path / "resume.pdf").exists()


def test_corrupt_pdf_returns_400(client, monkeypatch):
    api, session_factory, _ = client

    def broken(data):
        raise ValueError("EOF marker not found")

    monkeypatch.setattr(profile_api, "extract_pdf_text", broken)
    resp = api.post("/api/profile", files={"cv": ("bad.pdf", b"junk", "application/pdf")})

    assert resp.status_code == 400
    assert "Could not read the CV PDF" in resp.json()["detail"]
    with session_factory() as s:
        assert s.get(UserProfile, 1).cv_text == OLD_TEXT


def test_valid_new_cv_replaces_previous(client, monkeypatch):
    api, session_factory, tmp_path = client
    monkeypatch.setattr(profile_api, "extract_pdf_text", lambda data: NEW_TEXT)

    resp = api.post("/api/profile", files={"cv": ("new.pdf", b"%PDF-text", "application/pdf")})

    assert resp.status_code == 200
    assert resp.json()["cv_filename"] == "new.pdf"
    assert resp.json()["has_cv"] is True
    with session_factory() as s:
        assert s.get(UserProfile, 1).cv_text == NEW_TEXT.strip()
    assert (tmp_path / "resume.pdf").read_bytes() == b"%PDF-text"
