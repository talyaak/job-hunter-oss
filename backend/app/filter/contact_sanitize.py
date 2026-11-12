import re

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import UserProfile

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.I)


def build_email_blocklist(db: Session) -> set[str]:
    emails: set[str] = set()
    if settings.apply_email:
        emails.add(settings.apply_email.lower().strip())
    profile = db.get(UserProfile, 1)
    if profile:
        for text in (profile.cv_text, profile.profile_markdown):
            if text:
                emails.update(m.lower() for m in _EMAIL_RE.findall(text))
    return emails


def sanitize_contact_email(email: str | None, blocklist: set[str]) -> str | None:
    if not email:
        return None
    normalized = email.lower().strip()
    return None if normalized in blocklist else email.strip()
