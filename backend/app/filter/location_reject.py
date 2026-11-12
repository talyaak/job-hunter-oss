"""Location filter driven by user preferences.

If neither ``allowed_location_signals`` nor ``blocked_location_markers`` is set, nothing is rejected.
A job mentioning an allowed signal is always kept; otherwise a blocked marker rejects it.
"""

from app.preferences import Preferences, compile_keyword_patterns


def is_location_rejected(
    title: str,
    description: str,
    location: str | None = None,
    prefs: Preferences | None = None,
) -> tuple[bool, str | None]:
    prefs = prefs or Preferences()
    if not prefs.blocked_location_markers:
        return False, None

    text = " ".join(part for part in (location, title, (description or "")[:2000]) if part)
    if not text.strip():
        return False, None

    for pattern, _ in compile_keyword_patterns(prefs.allowed_location_signals):
        if pattern.search(text):
            return False, None

    for pattern, marker in compile_keyword_patterns(prefs.blocked_location_markers):
        if pattern.search(text):
            return True, f"Job location outside target market: {marker}"

    return False, None
