import re
from urllib.parse import urlparse, urlunparse

_SUFFIX_RE = re.compile(
    r"\b(inc|ltd|limited|corp|corporation|llc|co|israel|il)\b\.?", re.I
)
_NOISE_RE = re.compile(r"[^a-z0-9]+")


def normalize_company(name: str) -> str:
    s = (name or "").lower().strip()
    s = _SUFFIX_RE.sub("", s)
    return _NOISE_RE.sub("", s)


_COMEET_SUFFIX = re.compile(r"\s+at\s+.+?\s*-\s*comeet\s*$", re.I)
_REMOTE_SUFFIX = re.compile(r"\s+-\s*remote\s*$", re.I)


def normalize_title(title: str) -> str:
    s = (title or "").lower().strip()
    s = _COMEET_SUFFIX.sub("", s)
    s = _REMOTE_SUFFIX.sub("", s)
    s = re.sub(r"\s+-\s*comeet\s*$", "", s, flags=re.I)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", s)
    s = _NOISE_RE.sub(" ", s)
    return " ".join(s.split())


def job_fingerprint(company: str, title: str) -> str:
    return f"{normalize_company(company)}|{normalize_title(title)}"


def normalize_job_url(url: str) -> str:
    p = urlparse((url or "").strip())
    if not p.netloc:
        return (url or "").strip().lower()
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", "", ""))
