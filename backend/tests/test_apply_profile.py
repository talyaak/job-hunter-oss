from app.apply_profile import build_apply_profile
from app.config import settings


def test_build_apply_profile_from_cv(monkeypatch):
    for field in ("apply_email", "apply_full_name", "apply_phone", "apply_linkedin_url", "apply_location"):
        monkeypatch.setattr(settings, field, "")

    cv = """
Alex Morgan
alex@example.com
+1 415 555 2671
https://linkedin.com/in/alexmorgan
https://github.com/alexmorgan
"""
    p = build_apply_profile(cv, None)
    assert p.full_name == "Alex Morgan"
    assert p.email == "alex@example.com"
    assert "linkedin.com/in/alexmorgan" in p.linkedin_url
    assert p.phone.startswith("+1")
    assert p.first_name == "Alex"
    assert p.last_name == "Morgan"


def test_no_hardcoded_fallbacks(monkeypatch):
    for field in ("apply_email", "apply_full_name", "apply_phone", "apply_linkedin_url", "apply_location"):
        monkeypatch.setattr(settings, field, "")
    p = build_apply_profile("", "")
    assert p.linkedin_url == "" and p.location == "" and p.phone == ""
