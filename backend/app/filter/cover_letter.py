import json

from app.config import settings
from app.llm.client import generate_text
from app.llm.prompts import render



_TONE = {"professional": "professional and direct", "concise": "concise and punchy", "warm": "warm but professional"}
_WORD_LIMIT = {"short": 120, "medium": 220}


def generate_cover_letter(
    *,
    cv_text: str,
    profile_md: str,
    job_title: str,
    company: str,
    match_reason: str,
    stack_match: list[str],
    match_evaluation: dict,
    tone: str = "professional",
    length: str = "medium",
    instructions: str = "",
) -> str:
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY not configured")

    tone_label = _TONE.get(tone, _TONE["professional"])
    word_limit = _WORD_LIMIT.get(length, _WORD_LIMIT["medium"])
    strengths = match_evaluation.get("strengths") or []
    strengths_text = "; ".join(strengths[:4]) if strengths else match_reason[:400]

    extra = ""
    if instructions.strip():
        extra = (
            "\n\nAdditional instructions from the candidate "
            "(follow when compatible with CV facts; do not invent new claims):\n"
            + instructions.strip()[:1500]
        )

    prompt = render(
        "cover_letter",
        tone=tone_label,
        word_limit=str(word_limit),
        title=job_title,
        company=company,
        match_reason=match_reason[:800],
        stack=", ".join(stack_match[:8]) or "See CV",
        strengths=strengths_text,
        cv=cv_text[:8000],
        profile=profile_md[:4000],
        extra_instructions=extra,
    )
    resp_text = generate_text(prompt, temperature=0.4, max_output_tokens=1024)
    text = (resp_text or "").strip()
    if not text:
        raise ValueError("Empty cover letter response")
    return text


def parse_stack_match(raw) -> list[str]:
    if isinstance(raw, str):
        return json.loads(raw) if raw else []
    return raw or []
