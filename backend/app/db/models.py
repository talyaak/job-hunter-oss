import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PlatformSource(str, enum.Enum):
    linkedin = "linkedin"
    indeed = "indeed"
    glassdoor = "glassdoor"
    google = "google"


class RecruiterType(str, enum.Enum):
    direct = "direct"
    third_party = "third_party"


class WorkplaceType(str, enum.Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"
    unknown = "unknown"


class ApplicationStatus(str, enum.Enum):
    hidden = "hidden"
    saved = "saved"
    applied = "applied"


class IngestionTrigger(str, enum.Enum):
    cron = "cron"
    manual = "manual"


class IngestionStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class RejectStage(str, enum.Enum):
    location = "location"
    hard_title = "hard_title"
    dedupe = "dedupe"
    embedding_filter = "embedding_filter"
    gemma_filter = "gemma_filter"
    llm_score = "llm_score"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cv_text: Mapped[str | None] = mapped_column(Text)
    profile_markdown: Mapped[str | None] = mapped_column(Text)
    cv_filename: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trigger: Mapped[IngestionTrigger] = mapped_column(Enum(IngestionTrigger))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[IngestionStatus] = mapped_column(Enum(IngestionStatus))
    raw_count: Mapped[int] = mapped_column(Integer, default=0)
    passed_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    leads: Mapped[list["Lead"]] = relationship(back_populates="run")
    rejects: Mapped[list["IngestionReject"]] = relationship(back_populates="run")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date_posted: Mapped[date | None] = mapped_column(Date, index=True)
    job_title: Mapped[str] = mapped_column(String(500))
    company: Mapped[str] = mapped_column(String(255))
    platform_source: Mapped[PlatformSource] = mapped_column(Enum(PlatformSource), index=True)
    submission_method: Mapped[str] = mapped_column(String(100))
    recruiter_type: Mapped[RecruiterType] = mapped_column(Enum(RecruiterType))
    workplace_type: Mapped[WorkplaceType] = mapped_column(Enum(WorkplaceType))
    company_size: Mapped[str] = mapped_column(String(100), default="Unknown")
    product_vertical: Mapped[str] = mapped_column(String(100), default="Unknown")
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_linkedin_url: Mapped[str | None] = mapped_column(String(500))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    match_reason: Mapped[str] = mapped_column(Text)
    match_evaluation: Mapped[str] = mapped_column(Text, default="{}")
    stack_match: Mapped[str] = mapped_column(Text, default="[]")
    relevance_score: Mapped[int | None] = mapped_column(Integer)
    application_status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.saved, index=True
    )
    job_url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    ingestion_run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    run: Mapped["IngestionRun | None"] = relationship(back_populates="leads")


class IngestionReject(Base):
    __tablename__ = "ingestion_rejects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_title: Mapped[str | None] = mapped_column(String(500))
    company: Mapped[str | None] = mapped_column(String(255))
    job_url: Mapped[str] = mapped_column(String(1000))
    reject_stage: Mapped[RejectStage] = mapped_column(Enum(RejectStage))
    reject_reason: Mapped[str] = mapped_column(Text)
    relevance_score: Mapped[int | None] = mapped_column(Integer)
    stack_match: Mapped[str | None] = mapped_column(Text)
    ingestion_run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    run: Mapped["IngestionRun"] = relationship(back_populates="rejects")


class JobEmbedding(Base):
    __tablename__ = "job_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    job_title: Mapped[str | None] = mapped_column(String(500))
    company: Mapped[str | None] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding_json: Mapped[str] = mapped_column(Text)
    source_stage: Mapped[str] = mapped_column(String(50), default="job")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class LinkedinSearchHistory(Base):
    __tablename__ = "linkedin_search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(200))
    hours: Mapped[int] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)
    response_json: Mapped[str] = mapped_column(Text)
    new_urls_json: Mapped[str | None] = mapped_column(Text)


class LinkedinSearchFilters(Base):
    __tablename__ = "linkedin_search_filters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ignore_text: Mapped[str] = mapped_column(String(2000))
    removed_keys_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
