"""Health checks shared by ``GET /api/health/deep`` and the ``python -m app.doctor`` CLI.

Each check returns pass / warn / fail / skip with a human fix hint. ``probe=True`` additionally makes
real (cheap) calls to Gemini, LinkedIn and ntfy.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Lead, UserProfile
from app.preferences import get_preferences

BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    name: str
    status: str  # pass | warn | fail | skip
    detail: str = ""
    fix: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _check_database(db: Session) -> Check:
    try:
        db.execute(text("SELECT 1"))
        leads = db.scalar(select(func.count()).select_from(Lead)) or 0
    except Exception as exc:  # noqa: BLE001
        return Check("database", "fail", str(exc), "Check DATABASE_URL and run `alembic upgrade head` in backend/")
    return Check("database", "pass", f"reachable, {leads} leads")


def _check_migrations(db: Session) -> Check:
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        head = ScriptDirectory.from_config(cfg).get_current_head()
        current = MigrationContext.configure(db.connection()).get_current_revision()
    except Exception as exc:  # noqa: BLE001
        return Check("migrations", "warn", f"could not inspect: {exc}")
    if current == head:
        return Check("migrations", "pass", f"at head {head}")
    return Check(
        "migrations",
        "warn",
        f"current={current} head={head}",
        "Run `cd backend && alembic upgrade head` (tables are also auto-created at startup)",
    )


def _check_access(local_only_hint: bool = True) -> list[Check]:
    out = []
    if settings.access_token:
        out.append(Check("access_token", "pass", "configured"))
    else:
        out.append(Check("access_token", "fail", "ACCESS_TOKEN is empty: the tunnel would be unprotected", "Run `npm run setup`"))
    in_docker = os.environ.get("JOB_HUNTER_DOCKER") == "1"  # ports are published on the host loopback only
    if settings.api_host not in ("127.0.0.1", "localhost", "::1") and not in_docker:
        out.append(
            Check(
                "bind_address",
                "warn",
                f"API_HOST={settings.api_host} exposes the API to your network",
                "Set API_HOST=127.0.0.1 unless you really need LAN access",
            )
        )
    else:
        out.append(Check("bind_address", "pass", f"API bound to {settings.api_host}"))
    return out


def _check_preferences(db: Session) -> Check:
    prefs = get_preferences(db)
    if not prefs.onboarding_complete:
        return Check("preferences", "warn", "onboarding not completed", "Run `npm run setup` or open the app's setup wizard")
    return Check("preferences", "pass", f"titles={prefs.target_titles}, location={prefs.search_location!r}, threshold={prefs.score_threshold}")


def _check_profile(db: Session) -> Check:
    p = db.get(UserProfile, 1)
    if p and p.cv_text:
        return Check("profile", "pass", f"CV uploaded ({p.cv_filename or 'unnamed'})")
    return Check("profile", "fail", "no CV uploaded", "Upload your CV PDF in the app (Dashboard > Profile) or via onboarding")


def _check_gemini(probe: bool) -> list[Check]:
    if not settings.gemini_api_key:
        return [Check("gemini_key", "fail", "GEMINI_API_KEY missing", "Create a key at https://aistudio.google.com/apikey and run `npm run setup`")]
    out = [Check("gemini_key", "pass", "configured")]
    if probe:
        try:
            from app.llm.client import embed_text, generate_text

            reply = generate_text("Reply with the single word OK.", max_output_tokens=16)
            if not reply.strip():
                raise ValueError("empty reply from the model")
            out.append(Check("gemini_generate", "pass", f"model {settings.gemini_model} replied {reply.strip()[:20]!r}"))
            vec = embed_text("health check")
            out.append(Check("gemini_embed", "pass", f"{settings.embedding_model} dim={len(vec)}"))
        except Exception as exc:  # noqa: BLE001
            out.append(Check("gemini_live", "fail", str(exc)[:300], "Check the key and quota; on a 404 the model was retired: run `npm run doctor -- --models` and set GEMINI_MODEL (e.g. gemini-flash-latest)"))
    return out


def _check_linkedin(probe: bool) -> Check:
    if not settings.linkedin_enabled:
        return Check("linkedin", "skip", "LINKEDIN_ENABLED=false")
    if not settings.linkedin_cookie_string:
        return Check("linkedin", "warn", "no li_at cookie: guest scraping only, descriptions may be truncated", "See docs/LINKEDIN.md to add LINKEDIN_COOKIE_STRING")
    if not probe:
        return Check("linkedin", "pass", "cookie configured (not probed)")
    from app.ingestion.linkedin_auth import check_linkedin_cookie

    ok, detail = check_linkedin_cookie()
    return Check("linkedin", "pass" if ok else "fail", detail, "" if ok else "Copy a fresh li_at cookie from a logged-in browser (docs/LINKEDIN.md)")


def _check_ntfy(probe: bool) -> Check:
    if not settings.ntfy_topic:
        return Check("ntfy", "skip", "NTFY_TOPIC not set: no push notifications", "Optional: run `npm run setup` to generate a private topic")
    if len(settings.ntfy_topic) < 12:
        return Check("ntfy", "warn", "topic is short and guessable", "Use a long random topic (setup generates one)")
    if probe:
        from app.notify import send_ntfy

        ok = send_ntfy("Job Hunter doctor", "Test notification", tags=["white_check_mark"])
        return Check("ntfy", "pass" if ok else "fail", "test notification sent" if ok else "publish failed", "" if ok else "Check NTFY_SERVER and network")
    return Check("ntfy", "pass", "topic configured (not probed)")


def _check_scheduler() -> Check:
    from app.scheduler.cron import scheduler_status

    if not settings.ingestion_enabled:
        return Check("scheduler", "skip", "INGESTION_ENABLED=false")
    st = scheduler_status()
    if st["running"] and st["jobs"]:
        return Check("scheduler", "pass", f"{len(st['jobs'])} cron jobs registered")
    if st["running"]:
        return Check("scheduler", "warn", "running with no jobs", "Set cron_hours in preferences")
    return Check("scheduler", "warn", "not running (normal when called outside the server process)")


def _check_deps() -> list[Check]:
    out = []
    out.append(
        Check("jobspy", "pass", "installed")
        if importlib.util.find_spec("jobspy")
        else Check("jobspy", "fail", "python-jobspy missing", "pip install -e backend")
    )
    if settings.google_playwright_enabled:
        out.append(
            Check("playwright", "pass", "installed")
            if importlib.util.find_spec("playwright")
            else Check("playwright", "fail", "playwright missing", "pip install playwright && playwright install chromium")
        )
    return out


def run_checks(db: Session, probe: bool = False) -> list[Check]:
    checks: list[Check] = [_check_database(db), _check_migrations(db)]
    checks += _check_access()
    checks += [_check_preferences(db), _check_profile(db)]
    checks += _check_gemini(probe)
    checks += [_check_linkedin(probe), _check_ntfy(probe), _check_scheduler()]
    checks += _check_deps()
    return checks


def summarize(checks: list[Check]) -> str:
    if any(c.status == "fail" for c in checks):
        return "fail"
    if any(c.status == "warn" for c in checks):
        return "warn"
    return "pass"
