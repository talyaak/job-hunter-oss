import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import IngestionReject, JobEmbedding, Lead, RejectStage
from app.ingestion.normalizer import RawJob
from app.llm.client import embed_text

JOB_TEXT_LIMIT = 2000
PROFILE_CHUNK_LIMIT = 1800


@dataclass
class SimilarityResult:
    score: float
    threshold: float
    reason: str
    passed: bool


@dataclass
class SimilarExample:
    job_title: str
    company: str
    outcome: str
    score: int | None
    reason: str
    similarity: float


def build_job_embedding_text(job: RawJob) -> str:
    return "\n".join(
        [
            f"Title: {job.job_title}",
            f"Company: {job.company}",
            f"Description: {(job.description or '')[:JOB_TEXT_LIMIT]}",
        ]
    ).strip()


def build_profile_chunks(cv_text: str, profile_md: str) -> list[str]:
    chunks = []
    for label, text in (("CV", cv_text), ("Profile", profile_md)):
        clean = " ".join((text or "").split())
        if not clean:
            continue
        for i in range(0, min(len(clean), PROFILE_CHUNK_LIMIT * 3), PROFILE_CHUNK_LIMIT):
            chunk = clean[i : i + PROFILE_CHUNK_LIMIT]
            if chunk:
                chunks.append(f"{label}: {chunk}")
    return chunks


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_embedding(raw: str) -> list[float]:
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [float(v) for v in values]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    return embed_text(text, task_type=task_type)


def embed_profile_chunks(chunks: list[str]) -> list[list[float]]:
    return [_embed_text(chunk, task_type="RETRIEVAL_QUERY") for chunk in chunks]


def get_or_create_job_embedding(db: Session, job: RawJob) -> list[float]:
    text = build_job_embedding_text(job)
    content_hash = _content_hash(text)
    existing = db.scalar(select(JobEmbedding).where(JobEmbedding.job_url == job.job_url))
    if existing and existing.content_hash == content_hash:
        parsed = _parse_embedding(existing.embedding_json)
        if parsed:
            return parsed

    embedding = _embed_text(text)
    now = datetime.utcnow()
    payload = json.dumps(embedding)
    if existing:
        existing.job_title = job.job_title
        existing.company = job.company
        existing.content_hash = content_hash
        existing.embedding_json = payload
        existing.updated_at = now
    else:
        db.add(
            JobEmbedding(
                job_url=job.job_url,
                job_title=job.job_title,
                company=job.company,
                content_hash=content_hash,
                embedding_json=payload,
                source_stage="job",
                created_at=now,
                updated_at=now,
            )
        )
    db.flush()
    return embedding


def evaluate_similarity(
    db: Session,
    job: RawJob,
    profile_embeddings: list[list[float]],
    threshold: float | None = None,
) -> SimilarityResult:
    threshold = settings.embedding_similarity_threshold if threshold is None else threshold
    job_embedding = get_or_create_job_embedding(db, job)
    score = max((_cosine(job_embedding, profile_embedding) for profile_embedding in profile_embeddings), default=0.0)
    passed = score >= threshold
    return SimilarityResult(
        score=score,
        threshold=threshold,
        passed=passed,
        reason=f"Embedding similarity {score:.3f} {'>=' if passed else '<'} threshold {threshold:.3f}",
    )


def _lead_examples(db: Session) -> list[tuple[str, str, str, int | None, str]]:
    rows = db.scalars(select(Lead)).all()
    return [
        (row.job_url, row.job_title, row.company, row.relevance_score, row.match_reason)
        for row in rows
    ]


def _reject_examples(db: Session) -> list[tuple[str, str, str, int | None, str]]:
    rows = db.scalars(
        select(IngestionReject).where(
            IngestionReject.reject_stage == RejectStage.llm_score,
            IngestionReject.relevance_score.is_not(None),
        )
    ).all()
    return [
        (row.job_url, row.job_title or "Unknown role", row.company or "Unknown company", row.relevance_score, row.reject_reason)
        for row in rows
    ]


def _load_embeddings(db: Session, urls: list[str]) -> dict[str, list[float]]:
    """One query per chunk instead of one per candidate."""
    out: dict[str, list[float]] = {}
    for i in range(0, len(urls), 500):
        chunk = urls[i : i + 500]
        rows = db.execute(
            select(JobEmbedding.job_url, JobEmbedding.embedding_json).where(JobEmbedding.job_url.in_(chunk))
        ).all()
        for url, raw in rows:
            parsed = _parse_embedding(raw)
            if parsed:
                out[url] = parsed
    return out


def retrieve_similar_examples(
    db: Session,
    job: RawJob,
    limit: int | None = None,
) -> list[SimilarExample]:
    """Calibration RAG: nearest previously scored leads/rejects, used as scoring context."""
    limit = settings.embedding_retrieve_examples if limit is None else limit
    if limit <= 0:
        return []

    job_embedding = get_or_create_job_embedding(db, job)
    leads = [row for row in _lead_examples(db) if row[0] != job.job_url]
    rejects = [row for row in _reject_examples(db) if row[0] != job.job_url]
    vectors = _load_embeddings(db, [row[0] for row in leads + rejects])

    candidates: list[SimilarExample] = []
    for outcome, rows in (("lead", leads), ("reject", rejects)):
        for job_url, title, company, score, reason in rows:
            vec = vectors.get(job_url)
            if vec is None:
                continue
            candidates.append(SimilarExample(title, company, outcome, score, reason, _cosine(job_embedding, vec)))

    candidates.sort(key=lambda item: item.similarity, reverse=True)
    return candidates[:limit]


def format_similar_examples(examples: list[SimilarExample]) -> str:
    if not examples:
        return "No similar scored examples available yet."

    lines = []
    for example in examples:
        score = "unscored" if example.score is None else f"{example.score}%"
        lines.append(
            f"- {example.job_title} @ {example.company}: prior {example.outcome}, "
            f"score {score}, similarity {example.similarity:.3f}. Reason: {example.reason[:300]}"
        )
    return "\n".join(lines)
