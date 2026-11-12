"""Hard rejects driven by user preferences (blocked titles/descriptions/companies, contract roles)."""

import re

from app.preferences import Preferences, compile_keyword_patterns

# Contract/temp signals, toggled by ``Preferences.reject_contract_roles``.
CONTRACT_TITLE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bContractor\b", re.I), "Contractor"),
    (re.compile(r"\bFreelance\b", re.I), "Freelance"),
    (re.compile(r"\bContract-to-Hire\b", re.I), "Contract-to-Hire"),
    (re.compile(r"\bContract to Hire\b", re.I), "Contract to Hire"),
    (re.compile(r"\b(?:Fixed[\s-]Term|Short[\s-]Term)\s+Contract\b", re.I), "Fixed-term contract"),
    (re.compile(r"\bContract\s+Role\b", re.I), "Contract role"),
    (re.compile(r"\bTemp(?:orary)?\s+(?:Role|Position|Worker)\b", re.I), "Temporary role"),
    (re.compile(r"\b1099\b"), "1099 contractor"),
    (re.compile(r"\bC2C\b"), "C2C contractor"),
    (re.compile(r"\(Contract\)", re.I), "Contract"),
]

# Description-only; specific signals so ordinary legal "contract" wording does not trigger.
CONTRACT_DESC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bcontractor(?:\s+role|\s+position)?\b", re.I), "Contractor role"),
    (re.compile(r"\bfreelance(?:\s+role|\s+position|\s+basis)?\b", re.I), "Freelance role"),
    (re.compile(r"\bcontract-to-hire\b", re.I), "Contract-to-hire"),
    (re.compile(r"\b\d+[\s-]*month\s+contract\b", re.I), "Fixed-term contract"),
    (re.compile(r"\b1099\s+contractor\b", re.I), "1099 contractor"),
    (re.compile(r"\bc2c\s+(?:only|contractor|position)\b", re.I), "C2C contractor"),
]


def is_hard_rejected(
    title: str,
    description: str = "",
    prefs: Preferences | None = None,
    company: str = "",
) -> tuple[bool, str | None]:
    prefs = prefs or Preferences()
    title_text = title or ""

    for pattern, word in compile_keyword_patterns(prefs.blocked_title_keywords):
        if pattern.search(title_text):
            return True, f"Title contains blocked keyword: {word}"

    if company and any(c.lower() == company.strip().lower() for c in prefs.blocked_companies):
        return True, f"Company is blocklisted: {company}"

    if prefs.reject_contract_roles:
        for pattern, label in CONTRACT_TITLE_PATTERNS:
            if pattern.search(title_text):
                return True, f"Title contains blocked keyword: {label}"

    desc_text = (description or "")[:2000]
    for pattern, word in compile_keyword_patterns(prefs.blocked_description_keywords):
        if pattern.search(desc_text):
            return True, f"Description contains blocked keyword: {word}"

    if prefs.reject_contract_roles:
        for pattern, label in CONTRACT_DESC_PATTERNS:
            if pattern.search(desc_text):
                return True, f"Description indicates blocked role type: {label}"

    return False, None
