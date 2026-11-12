import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApplicationStatus, Lead, UserProfile
from app.db.session import get_db
from app.filter.contact_sanitize import build_email_blocklist, sanitize_contact_email
from app.filter.cover_letter import generate_cover_letter, parse_stack_match
from app.filter.dedupe import dedupe_leads
from app.schemas import CoverLetterIn, CoverLetterOut, LeadCountsOut, LeadListOut, LeadOut, LeadPatch

router = APIRouter(prefix="/api/leads", tags=["leads"])


def _lead_out(lead: Lead, blocklist: set[str]) -> LeadOut:
    out = LeadOut.model_validate(lead)
    out.contact_email = sanitize_contact_email(out.contact_email, blocklist)
    return out


def _lead_counts(db: Session) -> LeadCountsOut:
    items = dedupe_leads(db.scalars(select(Lead)).all())
    saved = sum(1 for l in items if l.application_status == ApplicationStatus.saved)
    applied = sum(1 for l in items if l.application_status == ApplicationStatus.applied)
    hidden = sum(1 for l in items if l.application_status == ApplicationStatus.hidden)
    return LeadCountsOut(total=len(items), saved=saved, applied=applied, hidden=hidden)


@router.get("", response_model=LeadListOut)
def list_leads(
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    blocklist = build_email_blocklist(db)
    status_filter: ApplicationStatus | None = None
    if status:
        try:
            status_filter = ApplicationStatus(status)
        except ValueError:
            pass

    q = select(Lead).order_by(Lead.date_posted.desc().nullslast(), Lead.created_at.desc())
    if status_filter:
        q = q.where(Lead.application_status == status_filter)

    items = dedupe_leads(db.scalars(q).all())
    total = len(items)
    page = items[offset : offset + limit]
    out = [_lead_out(lead, blocklist) for lead in page]
    return LeadListOut(items=out, total=total, counts=_lead_counts(db))


@router.post("/{lead_id}/cover-letter", response_model=CoverLetterOut)
def create_cover_letter(lead_id: int, body: CoverLetterIn, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    profile = db.get(UserProfile, 1)
    if not profile or not profile.cv_text or not profile.profile_markdown:
        raise HTTPException(400, "Upload CV and profile before generating a cover letter")

    eval_data: dict = {}
    if lead.match_evaluation:
        try:
            eval_data = json.loads(lead.match_evaluation) if isinstance(lead.match_evaluation, str) else lead.match_evaluation
        except json.JSONDecodeError:
            eval_data = {}

    try:
        text = generate_cover_letter(
            cv_text=profile.cv_text,
            profile_md=profile.profile_markdown,
            job_title=lead.job_title,
            company=lead.company,
            match_reason=lead.match_reason,
            stack_match=parse_stack_match(lead.stack_match),
            match_evaluation=eval_data,
            tone=body.tone,
            length=body.length,
            instructions=body.instructions,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Cover letter generation failed: {e}") from e

    return CoverLetterOut(lead_id=lead_id, cover_letter=text)


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return _lead_out(lead, build_email_blocklist(db))


@router.patch("/{lead_id}", response_model=LeadOut)
def patch_lead(lead_id: int, body: LeadPatch, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.application_status = body.application_status
    db.commit()
    db.refresh(lead)
    return _lead_out(lead, build_email_blocklist(db))
