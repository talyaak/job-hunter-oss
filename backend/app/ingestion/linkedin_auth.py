import json
import logging
import random
import re
import time

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def parse_cookie_string(raw: str) -> dict[str, str]:
    """Accept a bare li_at value, ``li_at=...`` or a full ``Cookie:`` header."""
    raw = (raw or "").strip()
    if not raw:
        return {}
    if "li_at" in raw and "=" in raw:
        cookies: dict[str, str] = {}
        for part in raw.replace("Cookie:", "").split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies
    return {"li_at": raw}


def build_linkedin_client() -> httpx.Client | None:
    """Authenticated client for fetching full job descriptions. Needs the ``li_at`` session cookie only."""
    if not settings.linkedin_enabled:
        return None
    cookies = parse_cookie_string(settings.linkedin_cookie_string)
    if not cookies:
        return None
    return httpx.Client(cookies=cookies, timeout=30, headers={"User-Agent": _UA}, follow_redirects=False)


def check_linkedin_cookie() -> tuple[bool, str]:
    """Cheap validity probe: a live session gets 200 on /feed/, an expired one is redirected to login."""
    client = build_linkedin_client()
    if client is None:
        return False, "No LINKEDIN_COOKIE_STRING configured (guest scraping still works, descriptions may be shorter)"
    try:
        r = client.get("https://www.linkedin.com/feed/")
    except Exception as exc:  # noqa: BLE001
        return False, f"Request failed: {exc}"
    finally:
        client.close()
    if r.status_code == 200:
        return True, "li_at cookie accepted"
    location = r.headers.get("location", "")
    if r.status_code in (301, 302, 303) and ("login" in location or "authwall" in location or "checkpoint" in location):
        return False, "Cookie expired or invalid: LinkedIn redirected to login. Copy a fresh li_at from your browser."
    return False, f"Unexpected response {r.status_code}"


def polite_delay() -> None:
    base = max(0.0, settings.linkedin_enrich_delay_seconds)
    if base:
        time.sleep(base + random.uniform(0, base))


def _strip_html(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _read_json_string_at(html: str, start: int) -> tuple[str | None, int]:
    if start >= len(html) or html[start] != '"':
        return None, start
    i = start + 1
    parts: list[str] = []
    while i < len(html):
        ch = html[i]
        if ch == "\\":
            if i + 1 >= len(html):
                return None, i
            parts.append(html[i : i + 2])
            i += 2
            continue
        if ch == '"':
            try:
                return json.loads(f'"{"".join(parts)}"'), i + 1
            except json.JSONDecodeError:
                return None, i + 1
        parts.append(ch)
        i += 1
    return None, i


def extract_linkedin_description(html: str) -> str | None:
    m = re.search(r'"description"\s*:\s*\{\s*"text"\s*:\s*"', html)
    if m:
        text, _ = _read_json_string_at(html, m.end() - 1)
        if text and len(text.strip()) > 20:
            return text.strip()

    m = re.search(
        r'class="[^"]*show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>',
        html,
        re.S | re.I,
    )
    if m:
        text = _strip_html(m.group(1))
        if len(text) > 20:
            return text

    return None


def enrich_description(job_url: str, client: httpx.Client | None) -> str | None:
    if not client or "linkedin.com" not in job_url:
        return None
    try:
        r = client.get(job_url)
        if r.status_code == 200:
            return extract_linkedin_description(r.text)
    except Exception:
        pass
    return None
