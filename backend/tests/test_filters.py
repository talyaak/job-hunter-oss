from app.filter.dedupe import dedupe_leads
from app.filter.hard_reject import is_hard_rejected
from app.filter.location_reject import is_location_rejected
from app.preferences import Preferences

PREFS = Preferences(blocked_title_keywords=["Data Engineer", "AI Training", "QA"])
from app.filter.job_fingerprint import job_fingerprint


def test_job_fingerprint_same_company_different_url():
    a = job_fingerprint("Acme", "Full Stack Developer")
    b = job_fingerprint("Acme Ltd.", "Full Stack Developer")
    assert a == b


def test_job_fingerprint_strips_comeet_suffix():
    a = job_fingerprint("Globex", "AI Applied Engineer at Globex - Comeet")
    b = job_fingerprint("Globex", "AI Applied Engineer")
    assert a == b


def test_dedupe_leads_keeps_highest_score():
    class Row:
        def __init__(self, company, title, score, created_at):
            self.company = company
            self.job_title = title
            self.relevance_score = score
            self.created_at = created_at
            self.date_posted = None

    rows = [
        Row("Acme", "Backend Developer", 88, 1),
        Row("Acme", "Backend Developer", 91, 2),
    ]
    out = dedupe_leads(rows)
    assert len(out) == 1
    assert out[0].relevance_score == 91


def test_hard_reject_data_engineer():
    rejected, reason = is_hard_rejected("Mid Data Engineer", prefs=PREFS)
    assert rejected
    assert "Data Engineer" in (reason or "")


def test_hard_reject_contractor_title():
    rejected, _ = is_hard_rejected("Full Stack Developer (Contract)")
    assert rejected


def test_hard_reject_contractor_description():
    rejected, reason = is_hard_rejected(
        "Software Engineer",
        "We are hiring a 12-month contract role for our platform team.",
    )
    assert rejected
    assert "contract" in (reason or "").lower()


def test_hard_reject_allows_regular_engineer():
    rejected, _ = is_hard_rejected("Full Stack Developer")
    assert not rejected


def test_hard_reject_ai_training():
    rejected, reason = is_hard_rejected("AI Training Specialist", prefs=PREFS)
    assert rejected
    assert "AI Training" in (reason or "")


def test_hard_reject_defaults_do_not_block_normal_titles():
    rejected, _ = is_hard_rejected("Senior Data Engineer")
    assert not rejected  # no personal blocklist ships by default


def test_hard_reject_company_blocklist():
    prefs = Preferences(blocked_companies=["Initech"])
    rejected, reason = is_hard_rejected("Software Engineer", "", prefs, company="initech")
    assert rejected and "blocklisted" in (reason or "")


def test_hard_reject_contract_toggle_off():
    prefs = Preferences(reject_contract_roles=False)
    rejected, _ = is_hard_rejected("Developer (Contract)", prefs=prefs)
    assert not rejected


def test_blocked_keyword_is_escaped_not_regex():
    prefs = Preferences(blocked_title_keywords=["C++ (Legacy)"])
    assert is_hard_rejected("Senior C++ (Legacy) Engineer", prefs=prefs)[0]
    assert not is_hard_rejected("Senior CXX Legacy Engineer", prefs=prefs)[0]


def test_location_filter_off_by_default():
    assert is_location_rejected("Engineer", "Based in Mumbai", "Mumbai, India") == (False, None)


def test_location_filter_blocks_unless_allowed_signal():
    prefs = Preferences(blocked_location_markers=["Mumbai"], allowed_location_signals=["Remote"])
    assert is_location_rejected("Engineer", "", "Mumbai, India", prefs)[0]
    assert not is_location_rejected("Engineer", "Remote friendly, Mumbai office", "Mumbai", prefs)[0]
