"""LLM job scoring: the model rates five dimensions, the weighted total is computed in code."""

import json
import re

from pydantic import ValidationError

from app.filter.evaluation import LlmEvaluation, calculate_final_score, to_pipeline_result
from app.ingestion.normalizer import RawJob
from app.llm.client import LlmNotConfigured, generate_text
from app.llm.prompts import render
from app.preferences import Preferences, get_preferences
from app.config import settings


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def _deal_breaker_rules(prefs: Preferences) -> str:
    lines = ["DEAL-BREAKER POLICY:"]
    if prefs.ignore_education_deal_breakers:
        lines.append(
            "- Education: a missing or unstated degree must NOT be a deal_breaker. "
            "Lower hard_requirements_score and mention it in gaps instead."
        )
    else:
        lines.append("- Education: a missing mandatory degree may be a deal_breaker.")
    if prefs.ignore_tenure_deal_breakers:
        lines.append(
            "- Tenure: if the JD asks for N+ years and the CV shows less, note it in gaps/seniority_score; "
            "never a deal_breaker by itself."
        )
    else:
        lines.append("- Tenure: a large mandatory-years shortfall may be a deal_breaker.")
    return "\n".join(lines) + "\n"


def _extra_rules(prefs: Preferences) -> str:
    rules = [ln.strip() for ln in prefs.extra_scoring_rules.splitlines() if ln.strip()]
    return "".join(f"- {r.lstrip('-* ')}\n" for r in rules)


def build_score_prompt(
    job: RawJob,
    cv_text: str,
    profile_md: str,
    similar_examples: str,
    prefs: Preferences,
) -> str:
    return render(
        "score",
        cv=cv_text[:12000],
        profile=profile_md[:8000],
        title=job.job_title,
        company=job.company,
        description=job.description[:12000],
        submission_method=job.submission_method,
        similar_examples=similar_examples or "No similar scored examples available yet.",
        candidate_notes=prefs.candidate_notes.strip() or "None provided.",
        deal_breaker_rules=_deal_breaker_rules(prefs),
        extra_rules=_extra_rules(prefs),
    )


def score_job(
    job: RawJob,
    cv_text: str,
    profile_md: str,
    similar_examples: str = "",
    prefs: Preferences | None = None,
) -> dict:
    if not settings.gemini_api_key:
        raise LlmNotConfigured("GEMINI_API_KEY not configured")

    prefs = prefs or get_preferences()
    prompt = build_score_prompt(job, cv_text, profile_md, similar_examples, prefs)

    raw: dict | None = None
    eval_data: LlmEvaluation | None = None
    for attempt in range(2):
        text = generate_text(prompt, temperature=0, json_mode=True)
        try:
            raw = _parse_json(text)
            eval_data = LlmEvaluation.model_validate(raw)
            break
        except (json.JSONDecodeError, AttributeError, ValidationError):
            if attempt == 1:
                raise

    assert raw is not None and eval_data is not None
    final_score = calculate_final_score(eval_data.scores, prefs.weights)
    return to_pipeline_result(
        eval_data,
        final_score,
        job.submission_method,
        prefs.ignore_education_deal_breakers,
        prefs.ignore_tenure_deal_breakers,
    )
