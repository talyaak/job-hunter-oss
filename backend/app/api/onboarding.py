"""Onboarding endpoints used by the first-run wizard (and the `onboard` agent skill)."""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import UserProfile
from app.db.session import get_db
from app.envfile import mask, update_env
from app.preferences import get_preferences, save_preferences

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class EnvIn(BaseModel):
    gemini_api_key: str | None = None
    linkedin_cookie_string: str | None = None
    ntfy_topic: str | None = None
    serp_api_key: str | None = None


def _status(db: Session) -> dict:
    prefs = get_preferences(db)
    profile = db.get(UserProfile, 1)
    steps = [
        {"id": "gemini", "label": "Gemini API key", "done": bool(settings.gemini_api_key), "required": True},
        {"id": "profile", "label": "CV uploaded", "done": bool(profile and profile.cv_text), "required": True},
        {"id": "preferences", "label": "Search preferences", "done": prefs.onboarding_complete, "required": True},
        {"id": "linkedin", "label": "LinkedIn cookie (optional)", "done": bool(settings.linkedin_cookie_string), "required": False},
        {"id": "ntfy", "label": "Push notifications (optional)", "done": bool(settings.ntfy_topic), "required": False},
        {"id": "access", "label": "Tunnel access token", "done": bool(settings.access_token), "required": True},
    ]
    return {
        "complete": all(s["done"] for s in steps if s["required"]),
        "steps": steps,
        "secrets": {
            "gemini_api_key": mask(settings.gemini_api_key),
            "linkedin_cookie_string": mask(settings.linkedin_cookie_string),
            "ntfy_topic": mask(settings.ntfy_topic),
            "serp_api_key": mask(settings.serp_api_key),
        },
    }


@router.get("/status")
def onboarding_status(db: Session = Depends(get_db)):
    return _status(db)


@router.put("/env")
def set_env(body: EnvIn, db: Session = Depends(get_db)):
    mapping = {
        "GEMINI_API_KEY": body.gemini_api_key,
        "LINKEDIN_COOKIE_STRING": body.linkedin_cookie_string,
        "NTFY_TOPIC": body.ntfy_topic,
        "SERP_API_KEY": body.serp_api_key,
    }
    values = {k: v.strip() for k, v in mapping.items() if v is not None}
    if not values:
        raise HTTPException(400, "Nothing to update")
    update_env(values)
    return _status(db)


@router.post("/ntfy-topic")
def generate_ntfy_topic(db: Session = Depends(get_db)):
    """Generate a long random topic. Anyone who knows it can read your alerts, so keep it private."""
    topic = "jh-" + secrets.token_urlsafe(18).replace("_", "x").replace("-", "y")
    update_env({"NTFY_TOPIC": topic})
    return {"topic": topic, **_status(db)}


@router.post("/validate/gemini")
def validate_gemini():
    from app.llm.client import generate_text

    try:
        reply = generate_text("Reply with the single word OK.", max_output_tokens=16)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": str(exc)[:300]}
    if not reply.strip():
        return {"ok": False, "detail": "The model returned an empty reply"}
    return {"ok": True, "detail": reply.strip()[:40]}


@router.post("/validate/linkedin")
def validate_linkedin():
    from app.ingestion.linkedin_auth import check_linkedin_cookie

    ok, detail = check_linkedin_cookie()
    return {"ok": ok, "detail": detail}


@router.post("/complete")
def complete_onboarding(db: Session = Depends(get_db)):
    prefs = get_preferences(db)
    prefs.onboarding_complete = True
    save_preferences(db, prefs)
    return _status(db)
