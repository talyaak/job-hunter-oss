import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)


def send_ntfy(
    title: str,
    message: str,
    click: str | None = None,
    priority: int = 3,
    tags: list[str] | None = None,
) -> bool:
    if not settings.ntfy_topic:
        return False
    body: dict = {
        "topic": settings.ntfy_topic,
        "title": title,
        "message": message,
        "priority": priority,
        "tags": tags or [],
    }
    if click:
        body["click"] = click
    try:
        resp = httpx.post(settings.ntfy_server.rstrip("/"), json=body, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        log.warning("[ntfy] publish failed: %s", e)
        return False


def notify_new_lead(job_title: str, company: str, score: int, job_url: str) -> None:
    send_ntfy(
        title=f"New lead {score}: {company}",
        message=job_title,
        click=job_url,
        priority=4,
        tags=["briefcase"],
    )
