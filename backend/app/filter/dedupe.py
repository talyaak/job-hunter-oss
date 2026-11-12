import logging
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngestionReject, Lead, RejectStage
from app.filter.job_fingerprint import job_fingerprint, normalize_job_url

log = logging.getLogger(__name__)

_SCORED_REJECT_STAGES = (
    RejectStage.llm_score,
    RejectStage.embedding_filter,
    RejectStage.gemma_filter,
)


class DedupeIndex:
    def __init__(self, db: Session):
        self.lead_urls: set[str] = set()
        self.lead_fingerprints: set[str] = set()
        self.reject_fingerprints: set[str] = set()
        self.batch_urls: set[str] = set()
        self.batch_fingerprints: set[str] = set()

        for url in db.scalars(select(Lead.job_url)):
            self.lead_urls.add(url)
            self.lead_urls.add(normalize_job_url(url))

        for company, title in db.execute(select(Lead.company, Lead.job_title)):
            self.lead_fingerprints.add(job_fingerprint(company or "", title or ""))

        reject_rows = db.execute(
            select(IngestionReject.company, IngestionReject.job_title).where(
                IngestionReject.reject_stage.in_(_SCORED_REJECT_STAGES),
                IngestionReject.relevance_score.is_not(None),
            )
        )
        for company, title in reject_rows:
            self.reject_fingerprints.add(job_fingerprint(company or "", title or ""))

    def is_duplicate(self, job_url: str, company: str, title: str) -> tuple[bool, str | None]:
        norm_url = normalize_job_url(job_url)
        fp = job_fingerprint(company, title)

        if job_url in self.lead_urls or norm_url in self.lead_urls:
            return True, "Already in leads"
        if norm_url in self.batch_urls:
            return True, "Duplicate URL in sync batch"
        if fp in self.lead_fingerprints:
            return True, f"Duplicate role already in leads: {company} / {title}"
        if fp in self.batch_fingerprints:
            return True, f"Duplicate role in sync batch: {company} / {title}"
        if fp in self.reject_fingerprints:
            return True, f"Previously scored reject for: {company} / {title}"

        return False, None

    def register_seen(self, job_url: str, company: str, title: str) -> None:
        self.batch_urls.add(normalize_job_url(job_url))
        self.batch_fingerprints.add(job_fingerprint(company, title))

    def register_scored_reject(self, company: str, title: str) -> None:
        self.reject_fingerprints.add(job_fingerprint(company, title))

    def register_lead(self, job_url: str, company: str, title: str) -> None:
        self.lead_urls.add(job_url)
        self.lead_urls.add(normalize_job_url(job_url))
        fp = job_fingerprint(company, title)
        self.lead_fingerprints.add(fp)
        self.register_seen(job_url, company, title)


class LeadIndex:
    def __init__(self, leads: Iterable[Lead]):
        self._by_url: dict[str, Lead] = {}
        self._by_fingerprint: dict[str, Lead] = {}
        for lead in leads:
            self._by_url.setdefault(lead.job_url, lead)
            self._by_url.setdefault(normalize_job_url(lead.job_url), lead)
            self._by_fingerprint.setdefault(job_fingerprint(lead.company, lead.job_title), lead)

    def find(self, job_url: str, company: str, title: str) -> Lead | None:
        return (
            self._by_url.get(job_url)
            or self._by_url.get(normalize_job_url(job_url))
            or self._by_fingerprint.get(job_fingerprint(company, title))
        )


def is_duplicate(db: Session, job_url: str, company: str = "", title: str = "") -> tuple[bool, str | None]:
    index = DedupeIndex(db)
    return index.is_duplicate(job_url, company, title)


def _ranking(lead) -> tuple:
    # Unscored leads rank below every scored one.
    return (-1 if lead.relevance_score is None else lead.relevance_score, lead.created_at)


def dedupe_leads(leads: list) -> list:
    best: dict[str, object] = {}
    for lead in leads:
        key = job_fingerprint(lead.company, lead.job_title)
        existing = best.get(key)
        if existing is None or _ranking(lead) > _ranking(existing):
            best[key] = lead
    return sorted(
        best.values(),
        key=lambda l: (l.date_posted is not None, l.date_posted or l.created_at, l.created_at),
        reverse=True,
    )
