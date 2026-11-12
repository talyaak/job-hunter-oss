from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app import envfile
from app.config import settings
from app.db.models import Base
from app.db.session import get_db
from app.doctor import run_checks, summarize
from app.main import app


@pytest.fixture
def api(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override():
        with factory() as s:
            yield s

    env = tmp_path / ".env"
    monkeypatch.setattr(envfile, "ENV_FILE", env)
    # update_env's default path argument was bound at import time, so patch the callers' reference too
    real_update = envfile.update_env
    monkeypatch.setattr("app.api.onboarding.update_env", lambda values, path=env: real_update(values, path))
    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    yield client, factory, env
    app.dependency_overrides.clear()


def test_update_env_preserves_other_lines_and_quotes(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\nFOO=bar\nGEMINI_API_KEY=old\n", encoding="utf-8")
    envfile.update_env({"GEMINI_API_KEY": "new key with space", "NTFY_TOPIC": "abc"}, env)
    lines = env.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# comment" and lines[1] == "FOO=bar"
    assert 'GEMINI_API_KEY="new key with space"' in lines
    assert "NTFY_TOPIC=abc" in lines
    assert settings.gemini_api_key == "new key with space"
    settings.gemini_api_key = ""
    settings.ntfy_topic = ""


def test_update_env_rejects_unknown_keys(tmp_path):
    with pytest.raises(ValueError):
        envfile.update_env({"DATABASE_URL": "sqlite:///x"}, tmp_path / ".env")


def test_ensure_access_token_generates_once(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "access_token", "")
    env = tmp_path / ".env"
    first = envfile.ensure_access_token(env)
    assert len(first) >= 32 and f"ACCESS_TOKEN={first}" in env.read_text(encoding="utf-8")
    assert envfile.ensure_access_token(env) == first


def test_mask_never_reveals_full_secret():
    assert envfile.mask("abcdefghijklmnop").endswith("mnop") and "abcd" not in envfile.mask("abcdefghijklmnop")
    assert envfile.mask("") == ""


def test_onboarding_status_flow(api, monkeypatch):
    client, _, _ = api
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "ntfy_topic", "")
    status = client.get("/api/onboarding/status").json()
    assert status["complete"] is False
    assert {s["id"] for s in status["steps"] if s["required"]} == {"gemini", "profile", "preferences", "access"}

    r = client.put("/api/onboarding/env", json={"gemini_api_key": "fake-test-key-value-1234"})
    assert r.status_code == 200
    assert "fake-test-key-value-1234" not in r.text  # secrets are masked in responses
    assert r.json()["secrets"]["gemini_api_key"].endswith("1234")
    monkeypatch.setattr(settings, "gemini_api_key", "")


def test_ntfy_topic_generation_is_long_and_random(api, monkeypatch):
    client, _, env = api
    a = client.post("/api/onboarding/ntfy-topic").json()["topic"]
    b = client.post("/api/onboarding/ntfy-topic").json()["topic"]
    assert a != b and len(a) >= 20 and a.startswith("jh-")
    monkeypatch.setattr(settings, "ntfy_topic", "")


def test_preferences_endpoint_round_trip(api):
    client, _, _ = api
    body = client.get("/api/preferences").json()
    body["target_titles"] = ["SRE"]
    body["score_threshold"] = 70
    saved = client.put("/api/preferences", json=body).json()
    assert saved["target_titles"] == ["SRE"] and client.get("/api/preferences").json()["score_threshold"] == 70
    assert client.put("/api/preferences", json={**body, "score_threshold": 500}).status_code == 422


def test_insights_summary_shape(api):
    client, _, _ = api
    data = client.get("/api/insights/summary").json()
    assert set(data) >= {"threshold", "leads", "rejects", "recent_runs", "preferences"}
    assert set(data["leads"]["score_histogram"]) == {"0-49", "50-69", "70-79", "80-89", "90-100"}


def test_deep_health_reports_missing_pieces(api, monkeypatch):
    client, _, _ = api
    monkeypatch.setattr(settings, "gemini_api_key", "")
    body = client.get("/api/health/deep").json()
    names = {c["name"]: c for c in body["checks"]}
    assert body["status"] == "fail"
    assert names["gemini_key"]["status"] == "fail" and names["gemini_key"]["fix"]
    assert names["access_token"]["status"] == "pass"
    assert names["profile"]["status"] == "fail"


def test_doctor_flags_missing_access_token(api, monkeypatch):
    _, factory, _ = api
    monkeypatch.setattr(settings, "access_token", "")
    with factory() as db:
        names = {c.name: c for c in run_checks(db)}
    assert names["access_token"].status == "fail" and "unprotected" in names["access_token"].detail


def test_run_checks_summarize(api):
    _, factory, _ = api
    with factory() as db:
        checks = run_checks(db, probe=False)
    assert summarize(checks) in {"pass", "warn", "fail"}
    assert all(c.status in {"pass", "warn", "fail", "skip"} for c in checks)


def test_health_live_is_public_and_minimal():
    r = TestClient(app, headers={}).get("/api/health/live")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_no_personal_strings_in_source_tree():
    root = Path(__file__).resolve().parents[2]
    needles = ["talyaak", "tal.jacobov", "Spinomenal", "10.100.102", "Ya'akov", "Yaakov"]
    skip_dirs = {".venv", "node_modules", ".git", "__pycache__", "dist", ".pytest_cache"}
    hits = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".ico", ".pdf", ".db", ".svg", ".woff", ".woff2", ".lock"}:
            continue
        if path.name == "test_onboarding_doctor.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for needle in needles:
            if needle.lower() in text.lower():
                hits.append(f"{path.relative_to(root)}: {needle}")
    assert not hits, "personal data leaked into the release tree:\n" + "\n".join(hits)
