from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, IngestionReject, IngestionRun, IngestionStatus, IngestionTrigger, RejectStage
from app.filter.unscored_backlog import count_unscored_rejects, process_unscored_backlog


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        yield session


def _seed_unscored(db, job_url="https://linkedin.com/jobs/view/1", title="Data Engineer"):
    run = IngestionRun(
        trigger=IngestionTrigger.manual,
        started_at=datetime.utcnow(),
        status=IngestionStatus.completed,
        raw_count=1,
        passed_count=0,
    )
    db.add(run)
    db.commit()
    db.add(
        IngestionReject(
            job_title=title,
            company="Acme",
            job_url=job_url,
            reject_stage=RejectStage.llm_score,
            reject_reason="429 quota",
            relevance_score=None,
            ingestion_run_id=run.id,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()


def test_count_unscored(db_session):
    _seed_unscored(db_session)
    assert count_unscored_rejects(db_session) == 1


def test_dismiss_mode_clears_unscored(db_session):
    _seed_unscored(db_session)
    stats = process_unscored_backlog(db_session, mode="dismiss", limit=10)
    assert stats.processed == 1
    assert stats.dismissed == 1
    assert stats.remaining == 0


def test_auto_hard_filters_without_llm(db_session):
    from unittest.mock import patch

    from app.preferences import Preferences, save_preferences

    save_preferences(db_session, Preferences(blocked_title_keywords=["Data Engineer"]))
    _seed_unscored(db_session, title="Senior Data Engineer")
    with patch("app.filter.unscored_backlog._fetch_description", return_value=""):
        stats = process_unscored_backlog(db_session, mode="auto", limit=10)
    assert stats.processed == 1
    assert stats.hard_filtered == 1
    assert stats.remaining == 0