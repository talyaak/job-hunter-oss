import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.filter import gemini_scorer
from app.filter.evaluation import DimensionScores, ScoreDimension, calculate_final_score
from app.ingestion.normalizer import normalize_job
from app.preferences import DEFAULT_WEIGHTS, Preferences, get_preferences, save_preferences


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session


def _scores(**values):
    base = {k: 50 for k in DEFAULT_WEIGHTS}
    base.update(values)
    return DimensionScores(**{k: ScoreDimension(value=v, explanation="") for k, v in base.items()})


def test_defaults_are_neutral_and_valid():
    p = Preferences()
    assert p.target_titles == ["Software Engineer"]
    assert p.blocked_title_keywords == [] and p.blocked_location_markers == []
    assert abs(sum(p.weights.values()) - 1) < 1e-9
    assert p.search_term() == '("Software Engineer")'


def test_weights_are_normalised_and_validated():
    p = Preferences(weights={"hard_requirements_score": 2, "signal_score": 2})
    assert abs(sum(p.weights.values()) - 1) < 1e-9
    with pytest.raises(ValueError):
        Preferences(weights={k: 0 for k in DEFAULT_WEIGHTS})
    with pytest.raises(ValueError):
        Preferences(weights={"hard_requirements_score": -1})


def test_list_fields_are_cleaned_and_hours_validated():
    p = Preferences(target_titles=[" Dev ", "dev", "", "Ops"], cron_hours=[19, 3, 3, 25, -1])
    assert p.target_titles == ["Dev", "Ops"]
    assert p.cron_hours == [3, 19]


def test_preferences_round_trip(db):
    assert get_preferences(db) == Preferences()  # nothing stored yet -> defaults
    save_preferences(db, Preferences(target_titles=["Data Scientist"], score_threshold=65, search_location="Paris"))
    loaded = get_preferences(db)
    assert loaded.target_titles == ["Data Scientist"] and loaded.score_threshold == 65


def test_corrupt_stored_preferences_fall_back_to_defaults(db):
    from app.db.models import UserPreferences

    db.add(UserPreferences(id=1, data="{not json"))
    db.commit()
    assert get_preferences(db) == Preferences()


def test_final_score_is_weighted_sum_computed_in_code():
    scores = _scores(hard_requirements_score=100, domain_similarity_score=0, seniority_score=0, technology_score=0, signal_score=0)
    assert calculate_final_score(scores) == 50  # default weight 0.50
    custom = {**{k: 0.0 for k in DEFAULT_WEIGHTS}, "technology_score": 1.0}
    assert calculate_final_score(_scores(technology_score=80), custom) == 80


def _llm_payload(**overrides):
    payload = {
        "extracted": {},
        "scores": {k: {"value": 90, "explanation": "x"} for k in DEFAULT_WEIGHTS},
        "strengths": ["Great fit"],
        "deal_breakers": ["Requires Bachelor's degree"],
        "matched_technologies": ["Python"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_score_job_uses_stubbed_llm_and_preferences(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "k")
    seen = {}

    def fake_generate(prompt, **kwargs):
        seen["prompt"] = prompt
        return _llm_payload()

    monkeypatch.setattr(gemini_scorer, "generate_text", fake_generate)
    job = normalize_job(job_title="Engineer", company="Acme", job_url="https://x/1", description="Build things", platform_source="linkedin")
    prefs = Preferences(candidate_notes="Prefers remote product teams", extra_scoring_rules="Penalise on-call heavy roles")

    result = gemini_scorer.score_job(job, "CV text", "", "", prefs)

    assert result["relevance_score"] == 90
    assert result["hard_reject_override"] is False  # education deal-breaker ignored by default
    assert "Prefers remote product teams" in seen["prompt"]
    assert "- Penalise on-call heavy roles" in seen["prompt"]
    assert "[[" not in seen["prompt"], "all template placeholders must be substituted"
    assert "Israel" not in seen["prompt"]


def test_education_deal_breaker_kept_when_policy_off(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(gemini_scorer, "generate_text", lambda *a, **k: _llm_payload())
    job = normalize_job(job_title="E", company="A", job_url="https://x/2", description="d", platform_source="indeed")
    result = gemini_scorer.score_job(job, "CV", "", "", Preferences(ignore_education_deal_breakers=False))
    assert result["hard_reject_override"] is True


def test_score_job_retries_once_on_bad_json(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "k")
    replies = iter(["not json", _llm_payload(deal_breakers=[])])
    monkeypatch.setattr(gemini_scorer, "generate_text", lambda *a, **k: next(replies))
    job = normalize_job(job_title="E", company="A", job_url="https://x/3", description="d", platform_source="indeed")
    assert gemini_scorer.score_job(job, "CV", "", "", Preferences())["relevance_score"] == 90


def test_score_job_requires_key(monkeypatch):
    from app.config import settings
    from app.llm.client import LlmNotConfigured

    monkeypatch.setattr(settings, "gemini_api_key", "")
    job = normalize_job(job_title="E", company="A", job_url="https://x/4", description="d", platform_source="indeed")
    with pytest.raises(LlmNotConfigured):
        gemini_scorer.score_job(job, "CV", "", "", Preferences())


def test_prompt_templates_have_no_personal_data():
    from pathlib import Path

    import app.llm.prompts as prompts

    text = "".join(p.read_text(encoding="utf-8") for p in Path(prompts.__file__).parent.glob("*.md"))
    for needle in ("Israel", "Tel Aviv"):
        assert needle not in text


def test_generate_text_gives_thinking_models_headroom(monkeypatch):
    """Live finding: max_output_tokens=16 returned '' because thinking tokens count toward the limit."""
    from types import SimpleNamespace

    from app.config import settings
    from app.llm import client as llm

    captured = {}

    class FakeModels:
        def generate_content(self, model, contents, config):
            captured["max"] = config.max_output_tokens
            captured["model"] = model
            return SimpleNamespace(text="OK")

    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(models=FakeModels()))
    assert llm.generate_text("hi", max_output_tokens=16) == "OK"
    assert captured["max"] == 16 + llm.THINKING_HEADROOM
    assert captured["model"] == settings.gemini_model


def test_generate_text_retries_transient_errors_then_raises(monkeypatch):
    from types import SimpleNamespace

    from app.config import settings
    from app.llm import client as llm

    calls = {"n": 0}

    class FlakyModels:
        def generate_content(self, **kwargs):
            calls["n"] += 1
            raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(settings, "llm_max_retries", 3)
    monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(models=FlakyModels()))
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        llm.generate_text("hi")
    assert calls["n"] == 3

    calls["n"] = 0

    class BadKey:
        def generate_content(self, **kwargs):
            calls["n"] += 1
            raise RuntimeError("400 API key not valid")

    monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(models=BadKey()))
    with pytest.raises(RuntimeError):
        llm.generate_text("hi")
    assert calls["n"] == 1  # non-retryable errors are not retried


def test_client_pins_api_version(monkeypatch):
    """Live finding: google-genai 3.x defaults to v1, where '-latest' aliases 404."""
    import sys
    from types import ModuleType, SimpleNamespace

    from app.config import settings
    from app.llm import client as llm

    seen = {}

    class FakeClient:
        def __init__(self, api_key, http_options):
            seen["version"] = http_options.api_version

    fake_google = ModuleType("google")
    fake_genai = ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_genai.types = SimpleNamespace(HttpOptions=lambda api_version: SimpleNamespace(api_version=api_version))
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_genai.types)
    monkeypatch.setattr(settings, "gemini_api_key", "k-version-test")
    monkeypatch.setattr(llm, "_client", None)
    llm.get_client()
    assert seen["version"] == "v1beta"
    monkeypatch.setattr(llm, "_client", None)
