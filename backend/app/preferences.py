"""User preferences: everything that used to be hardcoded for one person.

Stored as a single JSON document in ``user_preferences`` (id=1). All fields have neutral defaults so a
fresh clone works before onboarding; onboarding fills in the real values.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db.models import UserPreferences
from app.db.session import SessionLocal

DEFAULT_WEIGHTS: dict[str, float] = {
    "hard_requirements_score": 0.50,
    "domain_similarity_score": 0.15,
    "seniority_score": 0.15,
    "technology_score": 0.10,
    "signal_score": 0.10,
}


def _clean_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        s = (v or "").strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


class Preferences(BaseModel):
    # --- What to search for ---
    target_titles: list[str] = Field(default_factory=lambda: ["Software Engineer"])
    search_location: str = "Remote"
    country: str = ""  # Indeed country name (e.g. "USA"); empty = JobSpy default
    hours_old: int | None = None  # overrides JOBSPY_HOURS_OLD when set

    # --- Location filter (both empty = no location filtering) ---
    allowed_location_signals: list[str] = Field(default_factory=list)
    blocked_location_markers: list[str] = Field(default_factory=list)

    # --- Hard rejects ---
    blocked_title_keywords: list[str] = Field(default_factory=list)  # e.g. Manager, QA, Intern
    blocked_description_keywords: list[str] = Field(default_factory=list)
    blocked_companies: list[str] = Field(default_factory=list)
    reject_contract_roles: bool = True

    # --- Scoring ---
    score_threshold: int = Field(default=80, ge=0, le=100)
    high_score_threshold: int = Field(default=90, ge=0, le=100)
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    ignore_education_deal_breakers: bool = True
    ignore_tenure_deal_breakers: bool = True
    candidate_notes: str = ""  # what you want / what you avoid; injected into the scoring prompt
    extra_scoring_rules: str = ""  # extra bullet rules for the scorer

    # --- Schedule ---
    cron_hours: list[int] = Field(default_factory=lambda: [10, 15, 19])
    timezone: str = ""  # empty = CRON_TIMEZONE env / UTC

    # --- Bookkeeping ---
    onboarding_complete: bool = False

    @field_validator(
        "target_titles",
        "allowed_location_signals",
        "blocked_location_markers",
        "blocked_title_keywords",
        "blocked_description_keywords",
        "blocked_companies",
    )
    @classmethod
    def _lists(cls, v: list[str]) -> list[str]:
        return _clean_list(v)

    @field_validator("cron_hours")
    @classmethod
    def _hours(cls, v: list[int]) -> list[int]:
        out = sorted({int(h) for h in v if 0 <= int(h) <= 23})
        return out

    @field_validator("weights")
    @classmethod
    def _weights(cls, v: dict[str, float]) -> dict[str, float]:
        merged = {k: float(v.get(k, DEFAULT_WEIGHTS[k])) for k in DEFAULT_WEIGHTS}
        if any(w < 0 for w in merged.values()):
            raise ValueError("weights must be non-negative")
        total = sum(merged.values())
        if total <= 0:
            raise ValueError("weights must not all be zero")
        return {k: w / total for k, w in merged.items()}  # normalise so they always sum to 1

    def search_term(self) -> str:
        """Boolean-style term used by LinkedIn/Indeed/Google queries."""
        titles = self.target_titles or ["Software Engineer"]
        return "(" + " OR ".join(f'"{t}"' for t in titles) + ")"


def _row_to_prefs(row: UserPreferences | None) -> Preferences:
    if not row or not row.data:
        return Preferences()
    try:
        return Preferences.model_validate(json.loads(row.data))
    except (json.JSONDecodeError, ValueError):
        return Preferences()


def get_preferences(db: Session | None = None) -> Preferences:
    if db is not None:
        return _row_to_prefs(db.get(UserPreferences, 1))
    with SessionLocal() as session:
        return _row_to_prefs(session.get(UserPreferences, 1))


def save_preferences(db: Session, prefs: Preferences) -> Preferences:
    row = db.get(UserPreferences, 1)
    if not row:
        row = UserPreferences(id=1, data="{}")
        db.add(row)
    row.data = prefs.model_dump_json()
    row.updated_at = datetime.utcnow()
    db.commit()
    return prefs


def compile_keyword_patterns(words: list[str]) -> list[tuple[re.Pattern[str], str]]:
    """Plain words/phrases -> case-insensitive, word-boundary regexes (user input is escaped)."""
    return [(re.compile(rf"(?<!\w){re.escape(w)}(?!\w)", re.I), w) for w in words if w.strip()]
