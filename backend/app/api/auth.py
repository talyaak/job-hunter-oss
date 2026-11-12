from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.config import settings
from app.security import (
    COOKIE_NAME,
    client_key,
    is_authorized,
    is_local_request,
    is_rate_limited,
    record_failure,
    token_matches,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SessionIn(BaseModel):
    token: str


@router.get("/status")
def auth_status(request: Request):
    scope = request.scope
    return {
        "authenticated": is_authorized(scope),
        "token_required": not (settings.local_trust and is_local_request(scope)),
        "token_configured": bool(settings.access_token),
    }


@router.post("/session")
def create_session(body: SessionIn, request: Request, response: Response):
    """Exchange the token from the ntfy link for an HttpOnly cookie so it never lingers in the URL."""
    key = client_key(request.scope)
    if is_rate_limited(key):
        raise HTTPException(429, "Too many failed attempts")
    if not token_matches(body.token):
        record_failure(key)
        raise HTTPException(401, "Invalid access token")
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https" or bool(
        request.headers.get("cf-visitor")
    )
    response.set_cookie(
        COOKIE_NAME,
        body.token,
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"authenticated": False}
