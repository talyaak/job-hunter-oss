from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.doctor import run_checks, summarize

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
def live():
    """Unauthenticated liveness probe (used by the dev scripts to wait for the server)."""
    return {"status": "ok"}


@router.get("")
def health():
    return {"status": "ok", "api_version": 3}


@router.get("/deep")
def deep(probe: bool = Query(False, description="Also call Gemini, LinkedIn and ntfy"), db: Session = Depends(get_db)):
    checks = run_checks(db, probe=probe)
    return {"status": summarize(checks), "checks": [c.as_dict() for c in checks]}
