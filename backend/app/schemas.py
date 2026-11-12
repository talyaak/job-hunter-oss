import json
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.db.models import ApplicationStatus, IngestionStatus, IngestionTrigger, PlatformSource


class LeadOut(BaseModel):
    id: int
    date_posted: date | None
    job_title: str
    company: str
    platform_source: PlatformSource
    submission_method: str
    recruiter_type: str
    workplace_type: str
    company_size: str
    product_vertical: str
    contact_name: str | None
    contact_linkedin_url: str | None
    contact_email: str | None
    match_reason: str
    match_evaluation: dict = {}
    stack_match: list[str]
    relevance_score: int | None
    application_status: ApplicationStatus
    job_url: str
    description: str
    created_at: datetime

    @field_validator("stack_match", mode="before")
    @classmethod
    def parse_stack(cls, v):
        if isinstance(v, str):
            return json.loads(v) if v else []
        return v or []

    @field_validator("match_evaluation", mode="before")
    @classmethod
    def parse_evaluation(cls, v):
        if isinstance(v, str):
            return json.loads(v) if v else {}
        return v or {}

    model_config = {"from_attributes": True}


class LeadCountsOut(BaseModel):
    total: int
    saved: int
    applied: int
    hidden: int


class LeadListOut(BaseModel):
    items: list[LeadOut]
    total: int
    counts: LeadCountsOut | None = None


class LeadPatch(BaseModel):
    application_status: ApplicationStatus


class CoverLetterIn(BaseModel):
    tone: str = "professional"
    length: str = "medium"
    instructions: str = ""


class CoverLetterOut(BaseModel):
    lead_id: int
    cover_letter: str


class RejectOut(BaseModel):
    id: int
    job_title: str | None
    company: str | None
    job_url: str
    reject_stage: str
    reject_reason: str
    relevance_score: int | None
    stack_match: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class RejectListOut(BaseModel):
    items: list[RejectOut]
    total: int


class UnscoredProcessOut(BaseModel):
    pending: int
    processed: int
    leads_created: int
    scored_rejected: int
    hard_filtered: int
    dismissed: int
    deduped: int
    quota_stopped: bool
    remaining: int


class IngestionRunOut(BaseModel):
    id: int
    trigger: IngestionTrigger
    started_at: datetime
    finished_at: datetime | None
    status: IngestionStatus
    raw_count: int
    passed_count: int
    error_message: str | None

    model_config = {"from_attributes": True}


class SyncStartOut(BaseModel):
    run_id: int


class SyncStatusOut(BaseModel):
    current: IngestionRunOut | None
    last_completed: IngestionRunOut | None


class ProfileOut(BaseModel):
    id: int
    cv_filename: str | None
    has_cv: bool
    has_profile: bool
    has_resume_file: bool = False
    updated_at: datetime | None


class ApplyProfileOut(BaseModel):
    full_name: str
    first_name: str
    last_name: str
    email: str
    phone: str
    location: str
    linkedin_url: str
    github_url: str
    portfolio_url: str
    has_resume_file: bool


class LinkedinSearchItem(BaseModel):
    job_title: str
    company: str
    location: str | None
    job_url: str
    date_posted: date | None
    lead_status: ApplicationStatus | None = None


class LinkedinSearchOut(BaseModel):
    query: str
    location: str
    hours: int
    total: int
    items: list[LinkedinSearchItem]


class LinkedinPostedAgoOut(BaseModel):
    posted_ago: str | None


class LinkedinSaveIn(BaseModel):
    job_title: str = Field(max_length=500)
    company: str = Field(max_length=255)
    job_url: str = Field(min_length=1, max_length=1000)
    date_posted: date | None = None
    status: Literal["saved", "applied"]


class LinkedinSaveOut(BaseModel):
    lead_id: int
    application_status: ApplicationStatus


class LinkedinSearchHistoryOut(BaseModel):
    term: str
    location: str
    hours: int
    fetched_at: datetime
    new_urls: list[str] | None
    response: LinkedinSearchOut


class LinkedinSearchFiltersIn(BaseModel):
    ignore_text: str = Field(default="", max_length=2000)
    removed_keys: list[Annotated[str, Field(max_length=1000)]] = Field(default_factory=list, max_length=1000)


class LinkedinSearchFiltersOut(BaseModel):
    ignore_text: str
    removed_keys: list[str]
    updated_at: datetime | None
