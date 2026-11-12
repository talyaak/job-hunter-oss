"""Single entry point for Gemini calls (google-genai SDK): retries, JSON mode, embeddings."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)

_client: Any = None
_client_key: str = ""


# Thinking models count their reasoning tokens against max_output_tokens; without headroom a small
# limit yields an empty reply (observed live: max_output_tokens=16 -> "").
THINKING_HEADROOM = 2048


class LlmNotConfigured(ValueError):
    pass


def get_client():
    """Lazy google-genai client; rebuilt when the API key changes (e.g. after onboarding)."""
    global _client, _client_key
    if not settings.gemini_api_key:
        raise LlmNotConfigured("GEMINI_API_KEY not configured")
    if _client is None or _client_key != settings.gemini_api_key:
        from google import genai
        from google.genai import types

        # v1beta exposes the newest models and the "-latest" aliases; newer SDK defaults to v1, which does not.
        _client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(api_version=settings.gemini_api_version),
        )
        _client_key = settings.gemini_api_key
    return _client


def _retryable(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        s in text
        for s in ("429", "500", "502", "503", "504", "unavailable", "deadline", "timeout", "resource_exhausted")
    )


def generate_text(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.0,
    json_mode: bool = False,
    max_output_tokens: int | None = None,
) -> str:
    from google.genai import types

    client = get_client()
    cfg: dict[str, Any] = {"temperature": temperature}
    if json_mode:
        cfg["response_mime_type"] = "application/json"
    if max_output_tokens:
        cfg["max_output_tokens"] = max_output_tokens + THINKING_HEADROOM
    config = types.GenerateContentConfig(**cfg)

    last: Exception | None = None
    attempts = max(1, settings.llm_max_retries)
    for attempt in range(attempts):
        try:
            resp = client.models.generate_content(
                model=model or settings.gemini_model, contents=prompt, config=config
            )
            return resp.text or ""
        except Exception as exc:  # noqa: BLE001 - the SDK raises many exception types
            last = exc
            if attempt + 1 >= attempts or not _retryable(exc):
                break
            log.warning("[LLM] retry %d after error: %s", attempt + 1, exc)
            time.sleep(2**attempt)
    assert last is not None
    raise last


def list_models() -> dict[str, list[str]]:
    """Model names the configured key can call, split into text-generation and embedding models."""
    client = get_client()
    generate: list[str] = []
    embed: list[str] = []
    for m in client.models.list():
        name = (m.name or "").removeprefix("models/")
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            generate.append(name)
        if "embedContent" in actions:
            embed.append(name)
    return {"generate": sorted(generate), "embed": sorted(embed)}


def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    from google.genai import types

    client = get_client()
    model = settings.embedding_model.strip().removeprefix("models/")
    resp = client.models.embed_content(
        model=model,
        contents=text,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return [float(v) for v in resp.embeddings[0].values]
