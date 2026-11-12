"""Exercises the data paths the `tips` and `calibrate` skills rely on, with seeded data."""

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.db.models import (
    ApplicationStatus,
    Base,
    IngestionReject,
    IngestionRun,
    IngestionStatus,
    IngestionTrigger,
    Lead,
    PlatformSource,
    RecruiterType,
    RejectStage,
    WorkplaceType,
)
from app.db.session import get_db
from app.main import app
from app.preferences import Preferences, save_preferences

NOW = datetime(2026, 11, 1, 12, 0, 0)


@pytest.fixture
def api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    with factory() as db:
        save_preferences(db, Preferences(score_threshold=80))
        run = IngestionRun(trigger=IngestionTrigger.manual, started_at=NOW, status=IngestionStatus.completed, raw_count=12, passed_count=3)
        db.add(run)
        db.flush()

        def lead(i, score, source=PlatformSource.linkedin):
            evaluation = {
                "scores": {k: {"value": score, "explanation": "x"} for k in (
                    "hard_requirements_score", "domain_similarity_score", "seniority_score", "technology_score", "signal_score")},
                "strengths": ["Strong stack match"],
                "gaps": ["No on-call experience"],
            }
            db.add(Lead(
                date_posted=None, job_title=f"Engineer {i}", company=f"Co{i}", platform_source=source,
                submission_method="Unknown", recruiter_type=RecruiterType.direct, workplace_type=WorkplaceType.remote,
                match_reason="r", match_evaluation=json.dumps(evaluation), stack_match="[]", relevance_score=score,
                application_status=ApplicationStatus.saved, job_url=f"https://x/lead/{i}", description="d",
                ingestion_run_id=run.id, created_at=NOW,
            ))

        for i, s in enumerate([95, 91, 84, 82]):
            lead(i, s)
        lead(9, 85, PlatformSource.indeed)

        def reject(i, stage, score, reason):
            db.add(IngestionReject(
                job_title=f"Reject {i}", company=f"Rc{i}", job_url=f"https://x/rej/{i}", reject_stage=stage,
                reject_reason=reason, relevance_score=score, stack_match=None, ingestion_run_id=run.id, created_at=NOW,
            ))

        reject(1, RejectStage.llm_score, 79, "Recruiter score 79%")
        reject(2, RejectStage.llm_score, 72, "Recruiter score 72%")
        reject(3, RejectStage.llm_score, 40, "Recruiter score 40%")
        reject(4, RejectStage.hard_title, None, "Title contains blocked keyword: Manager")
        reject(5, RejectStage.hard_title, None, "Title contains blocked keyword: Manager")
        reject(6, RejectStage.location, None, "Job location outside target market: Mumbai")
        db.commit()

    def override():
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_summary_gives_tips_skill_its_signals(api):
    data = api.get("/api/insights/summary").json()
    assert data["threshold"] == 80
    assert data["leads"]["total"] == 5
    assert data["leads"]["score_histogram"] == {"0-49": 0, "50-69": 0, "70-79": 0, "80-89": 3, "90-100": 2}
    assert data["leads"]["by_source"] == {"linkedin": 4, "indeed": 1}
    assert data["rejects"]["by_stage"] == {"llm_score": 3, "hard_title": 2, "location": 1}
    assert data["rejects"]["scored_near_miss_count"] == 2  # 79 and 72 are within 10 below the threshold
    reasons = dict((r, n) for r, n in data["rejects"]["top_filter_reasons"])
    assert reasons["Title contains blocked keyword: Manager"] == 2
    assert data["recent_runs"][0]["raw_count"] == 12
    assert data["preferences"]["score_threshold"] == 80


def test_calibrate_fetches_near_misses_with_the_documented_query(api):
    near = api.get("/api/rejects", params={"stage": "llm_score", "min_score": 65, "max_score": 79}).json()
    assert [i["relevance_score"] for i in near["items"]] == [79, 72]  # best first
    assert all(i["reject_reason"] for i in near["items"])
    # without an explicit stage a score filter implies the LLM stage
    implied = api.get("/api/rejects", params={"min_score": 65, "max_score": 79}).json()
    assert implied["total"] == 2


def test_calibrate_reads_dimension_scores_from_leads(api):
    items = api.get("/api/leads").json()["items"]
    assert len(items) == 5
    evaluation = items[0]["match_evaluation"]
    assert set(evaluation["scores"]) == {
        "hard_requirements_score", "domain_similarity_score", "seniority_score", "technology_score", "signal_score"
    }
    assert evaluation["gaps"] and evaluation["strengths"]


def test_tips_apply_flow_put_preferences_changes_only_agreed_fields(api):
    current = api.get("/api/preferences").json()
    proposal = {**current, "score_threshold": 75}  # what the skill would send after approval
    saved = api.put("/api/preferences", json=proposal).json()
    assert saved["score_threshold"] == 75
    assert saved["target_titles"] == current["target_titles"] and saved["weights"] == current["weights"]
    assert api.get("/api/insights/summary").json()["threshold"] == 75
