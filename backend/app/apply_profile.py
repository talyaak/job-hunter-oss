import re
from dataclasses import dataclass

from app.config import settings

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?<![\d-])(?:\+\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]\d{3}[\s\-.]?\d{3,4}(?!\d)")
_LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w\-_%]+/?", re.I)
_GITHUB_RE = re.compile(r"https?://(?:www\.)?github\.com/[\w\-]+/?", re.I)


@dataclass
class ApplyProfile:
    full_name: str
    email: str
    phone: str
    location: str
    linkedin_url: str
    github_url: str
    portfolio_url: str

    @property
    def first_name(self) -> str:
        parts = self.full_name.split()
        return parts[0] if parts else ""

    @property
    def last_name(self) -> str:
        parts = self.full_name.split()
        return " ".join(parts[1:]) if len(parts) > 1 else ""


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    m = pattern.search(text)
    return m.group(0).strip() if m else ""


def _guess_name(text: str) -> str:
    for line in text.splitlines()[:8]:
        line = line.strip()
        if not line or len(line) > 60:
            continue
        if "@" in line or line.lower().startswith("http"):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(w[0].isalpha() for w in words if w):
            return line
    return ""


def build_apply_profile(cv_text: str | None, profile_text: str | None) -> ApplyProfile:
    combined = "\n".join(filter(None, [cv_text or "", profile_text or ""]))

    email = settings.apply_email or _first_match(_EMAIL_RE, combined)
    phone = settings.apply_phone or _first_match(_PHONE_RE, combined)
    linkedin = settings.apply_linkedin_url or _first_match(_LINKEDIN_RE, combined)
    github = settings.apply_github_url or _first_match(_GITHUB_RE, combined)
    portfolio = settings.apply_portfolio_url or github
    full_name = settings.apply_full_name or _guess_name(combined)
    location = settings.apply_location

    return ApplyProfile(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        linkedin_url=linkedin,
        github_url=github,
        portfolio_url=portfolio,
    )
