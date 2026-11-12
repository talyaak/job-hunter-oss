"""Safe read/update of the repo-root ``.env`` (used by onboarding)."""

from __future__ import annotations

import re
import secrets
from pathlib import Path

from app.config import ENV_FILE, settings

# Keys the onboarding API is allowed to write, mapped to Settings attribute names.
WRITABLE_KEYS: dict[str, str] = {
    "GEMINI_API_KEY": "gemini_api_key",
    "LINKEDIN_COOKIE_STRING": "linkedin_cookie_string",
    "NTFY_TOPIC": "ntfy_topic",
    "NTFY_SERVER": "ntfy_server",
    "SERP_API_KEY": "serp_api_key",
    "ACCESS_TOKEN": "access_token",
}

_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def _quote(value: str) -> str:
    if value == "" or re.fullmatch(r"[A-Za-z0-9_./:@+,=-]+", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def update_env(values: dict[str, str], path: Path = ENV_FILE) -> None:
    """Upsert ``KEY=value`` lines, preserving comments and other keys. Updates live settings too."""
    for key in values:
        if key not in WRITABLE_KEYS:
            raise ValueError(f"{key} cannot be written through this API")

    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(values)
    out: list[str] = []
    for line in lines:
        m = _LINE.match(line)
        if m and m.group(1) in pending:
            key = m.group(1)
            out.append(f"{key}={_quote(pending.pop(key))}")
        else:
            out.append(line)
    for key, value in pending.items():
        out.append(f"{key}={_quote(value)}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")

    for key, value in values.items():
        setattr(settings, WRITABLE_KEYS[key], value)


def ensure_access_token(path: Path = ENV_FILE) -> str:
    """Return the access token, generating and persisting one on first run."""
    if settings.access_token:
        return settings.access_token
    token = secrets.token_urlsafe(32)
    update_env({"ACCESS_TOKEN": token}, path)
    return token


def mask(value: str) -> str:
    if not value:
        return ""
    return "*" * 8 + value[-4:] if len(value) > 8 else "*" * len(value)
