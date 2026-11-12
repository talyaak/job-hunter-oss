"""Recruiter-style CV ↔ Job evaluation framework."""

import re

from pydantic import BaseModel, Field, field_validator

# Default weights; users can override them in Preferences.weights (normalised to sum to 1).
SCORE_WEIGHTS = {
    "hard_requirements_score": 0.50,
    "domain_similarity_score": 0.15,
    "seniority_score": 0.15,
    "technology_score": 0.10,
    "signal_score": 0.10,
}

DIMENSION_KEYS = tuple(SCORE_WEIGHTS.keys())

_EDUCATION_DEAL_BREAKER = re.compile(
    r"\b(degree|bachelor|b\.?sc|b\.?s\.?\s*degree|master'?s?|phd|doctorate|diploma|"
    r"formal education|cs degree|computer science degree|academic degree)\b",
    re.I,
)

_TENURE_ONLY_DEAL_BREAKER = re.compile(
    r"^(?:missing\s+)?(?:minimum\s+)?(?:at\s+least\s+)?\d+\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+experience)?\.?$|"
    r"^(?:requires?|needs?)\s+\d+\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+experience)?\.?$|"
    r"^\d+[\s-]+\d+\s*years?\s+(?:of\s+)?experience\.?$",
    re.I,
)


def sanitize_deal_breakers(
    items: list[str],
    ignore_education: bool = True,
    ignore_tenure: bool = True,
) -> list[str]:
    out: list[str] = []
    for item in items:
        text = (item or "").strip()
        if not text:
            continue
        if ignore_education and _EDUCATION_DEAL_BREAKER.search(text):
            continue
        if ignore_tenure and _TENURE_ONLY_DEAL_BREAKER.match(text):
            continue
        if ignore_tenure and re.search(r"\b\d+\+?\s*(?:years?|yrs?)\b", text, re.I) and not re.search(
            r"\b(python|java|typescript|react|aws|kubernetes|clearance|hebrew|english|sql|node)\b",
            text,
            re.I,
        ):
            continue
        out.append(item)
    return out


class ScoreDimension(BaseModel):
    value: int = Field(ge=0, le=100)
    explanation: str = ""


class ExtractedRequirements(BaseModel):
    must_have_requirements: list[str] = Field(default_factory=list)
    nice_to_have_requirements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    seniority_expectation: str = ""
    domain_expectation: str = ""


class DimensionScores(BaseModel):
    hard_requirements_score: ScoreDimension
    domain_similarity_score: ScoreDimension
    seniority_score: ScoreDimension
    technology_score: ScoreDimension
    signal_score: ScoreDimension


class LlmEvaluation(BaseModel):
    extracted: ExtractedRequirements
    scores: DimensionScores
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    deal_breakers: list[str] = Field(default_factory=list)
    resume_recommendations: list[str] = Field(default_factory=list)
    interview_risks: list[str] = Field(default_factory=list)
    workplace_type: str = "unknown"
    company_size: str = "Unknown"
    product_vertical: str = "Unknown"
    recruiter_type: str = "direct"
    submission_method: str = "Unknown"
    contact_name: str | None = None
    contact_linkedin_url: str | None = None
    contact_email: str | None = None
    matched_technologies: list[str] = Field(default_factory=list)

    @field_validator("recruiter_type")
    @classmethod
    def recruiter_type_valid(cls, v: str) -> str:
        return v if v in ("direct", "third_party") else "direct"


def calculate_final_score(scores: DimensionScores, weights: dict[str, float] | None = None) -> int:
    """Weighted total computed in code; the model never computes the final score."""
    weights = weights or SCORE_WEIGHTS
    total = 0.0
    for key, weight in weights.items():
        dim = getattr(scores, key)
        total += dim.value * weight
    return round(total)


def compose_match_reason(eval_data: LlmEvaluation, final_score: int) -> str:
    headline = (
        f"Recruiter score {final_score}% — "
        f"hard reqs {eval_data.scores.hard_requirements_score.value}, "
        f"domain {eval_data.scores.domain_similarity_score.value}, "
        f"seniority {eval_data.scores.seniority_score.value}."
    )
    if eval_data.strengths:
        return f"{headline} {eval_data.strengths[0]}"
    return headline


def build_evaluation_payload(eval_data: LlmEvaluation, final_score: int) -> dict:
    return {
        "extracted": eval_data.extracted.model_dump(),
        "scores": {k: getattr(eval_data.scores, k).model_dump() for k in DIMENSION_KEYS},
        "final_score": final_score,
        "strengths": eval_data.strengths,
        "gaps": eval_data.gaps,
        "deal_breakers": eval_data.deal_breakers,
        "resume_recommendations": eval_data.resume_recommendations,
        "interview_risks": eval_data.interview_risks,
    }


def to_pipeline_result(
    eval_data: LlmEvaluation,
    final_score: int,
    submission_method_hint: str,
    ignore_education: bool = True,
    ignore_tenure: bool = True,
) -> dict:
    deal_breakers = sanitize_deal_breakers(eval_data.deal_breakers, ignore_education, ignore_tenure)
    eval_data.deal_breakers = deal_breakers
    has_deal_breakers = bool(deal_breakers)
    method = eval_data.submission_method
    if method == "Unknown" and submission_method_hint:
        method = submission_method_hint

    return {
        "relevance_score": final_score,
        "stack_match": eval_data.matched_technologies,
        "match_reason": compose_match_reason(eval_data, final_score),
        "match_evaluation": build_evaluation_payload(eval_data, final_score),
        "workplace_type": eval_data.workplace_type,
        "company_size": eval_data.company_size,
        "product_vertical": eval_data.product_vertical,
        "recruiter_type": eval_data.recruiter_type,
        "submission_method": method,
        "contact_name": eval_data.contact_name,
        "contact_linkedin_url": eval_data.contact_linkedin_url,
        "contact_email": eval_data.contact_email,
        "hard_reject_override": has_deal_breakers,
    }
