"""Guards against syntax/import errors in modules no other test touches (CLIs, onboarding, scripts)."""

import importlib
import pkgutil
import py_compile
from pathlib import Path

import pytest

import app

ROOT = Path(__file__).resolve().parents[2]


def test_every_app_module_imports():
    failures = []
    for mod in pkgutil.walk_packages(app.__path__, "app."):
        try:
            importlib.import_module(mod.name)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{mod.name}: {exc!r}")
    assert not failures, "\n".join(failures)


PY_FILES = sorted(p for p in (ROOT / "backend").rglob("*.py") if ".venv" not in p.parts and "node_modules" not in p.parts)


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_python_file_compiles(path):
    py_compile.compile(str(path), doraise=True)


def test_doctor_models_flag_with_stubbed_client(monkeypatch, capsys):
    from app import doctor_cli
    from app.llm import client

    monkeypatch.setattr(client, "list_models", lambda: {"generate": ["gemini-flash-latest"], "embed": ["gemini-embedding-001"]})
    assert doctor_cli.main(["--models"]) == 0
    out = capsys.readouterr().out
    assert "gemini-flash-latest" in out and "gemini-embedding-001" in out and "Current: GEMINI_MODEL=" in out
    assert doctor_cli.main(["--models", "--json"]) == 0


def test_onboard_cli_runs_non_interactively(monkeypatch, tmp_path, capsys):
    """`npm run setup -- --yes` path: creates .env, token, preferences, ntfy topic without prompting."""
    from app import envfile, onboard
    from app.config import settings

    env = tmp_path / ".env"
    (tmp_path / ".env.example").write_text("ACCESS_TOKEN=\n", encoding="utf-8")
    for mod in (onboard, envfile):
        monkeypatch.setattr(mod, "ENV_FILE", env, raising=False)
    monkeypatch.setattr(onboard, "REPO_ROOT", tmp_path)
    real_update, real_ensure = envfile.update_env, envfile.ensure_access_token
    monkeypatch.setattr(onboard, "update_env", lambda values, path=env: real_update(values, path))
    monkeypatch.setattr(onboard, "ensure_access_token", lambda path=env: real_ensure(path))
    monkeypatch.setattr(settings, "access_token", "")
    monkeypatch.setattr(settings, "ntfy_topic", "")

    try:
        code = onboard.main(["--yes", "--titles", "SRE, Platform Engineer", "--location", "Lisbon", "--skip-doctor"])
    finally:
        settings.ntfy_topic = ""
        settings.access_token = ""
        from app.db.models import UserPreferences
        from app.db.session import SessionLocal

        with SessionLocal() as db:  # keep the shared test DB pristine for other tests
            row = db.get(UserPreferences, 1)
            snapshot = row.data if row else None
    assert code == 0
    text = env.read_text(encoding="utf-8")
    assert "ACCESS_TOKEN=" in text and "NTFY_TOPIC=jh-" in text
    from app.preferences import get_preferences

    prefs = get_preferences()
    assert prefs.target_titles == ["SRE", "Platform Engineer"] and prefs.search_location == "Lisbon"
    assert prefs.onboarding_complete is True
    with SessionLocal() as db:
        db.query(UserPreferences).delete()
        db.commit()
    assert "access token ready" in capsys.readouterr().out.lower()
