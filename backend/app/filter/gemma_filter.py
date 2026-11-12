import json
import re
from dataclasses import dataclass

from app.config import settings
from app.llm.client import generate_text
from app.llm.prompts import render
from app.ingestion.normalizer import RawJob




@dataclass
class GemmaFilterResult:
    passed: bool
    decision: str
    reason: str
    raw_text: str = ""


def _candidate_summary(cv_text: str, profile_md: str) -> str:
    text = " ".join(f"{cv_text}\n{profile_md}".split())
    return text[:5000]


def _parse_decision(text: str) -> tuple[str, str]:
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```\w*\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean)

    try:
        parsed = json.loads(clean)
        decision = str(parsed.get("decision", "")).strip().lower()
        reason = str(parsed.get("reason", "")).strip()
        if decision in {"yes", "no"}:
            return decision, reason or f"Gemma returned {decision}"
    except json.JSONDecodeError:
        pass

    lowered = clean.lower()
    no_match = re.search(r"\b(no|reject|not plausibly qualified|not qualified)\b", lowered)
    yes_match = re.search(r"\b(yes|pass|plausibly qualified|qualified)\b", lowered)
    if no_match and not yes_match:
        return "no", clean[:300] or "Gemma hard-no filter rejected the job"
    if yes_match:
        return "yes", clean[:300] or "Gemma passed the job"
    return "yes", "Gemma response was unclear; passing to full scorer"


def evaluate_gemma_filter(job: RawJob, cv_text: str, profile_md: str) -> GemmaFilterResult:
    if not settings.gemini_api_key:
        return GemmaFilterResult(True, "yes", "GEMINI_API_KEY not configured; passing to full scorer")

    prompt = render(
        "prefilter",
        profile_summary=_candidate_summary(cv_text, profile_md),
        title=job.job_title,
        company=job.company,
        description=(job.description or "")[:5000],
    )

    try:
        raw_text = generate_text(prompt, model=settings.gemma_model, temperature=0)
        decision, reason = _parse_decision(raw_text)
    except Exception as exc:
        return GemmaFilterResult(True, "yes", f"Gemma filter failed open: {exc}")

    return GemmaFilterResult(
        passed=decision != "no",
        decision=decision,
        reason=reason,
        raw_text=raw_text,
    )
