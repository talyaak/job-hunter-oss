from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.apply_profile import build_apply_profile
from app.db.models import UserProfile
from app.db.session import get_db
from app.filter.cv_parser import extract_pdf_text
from app.schemas import ApplyProfileOut, ProfileOut

router = APIRouter(prefix="/api/profile", tags=["profile"])

RESUME_PATH = Path(__file__).resolve().parents[2] / "data" / "resume.pdf"


def _to_out(p: UserProfile | None) -> ProfileOut:
    if not p:
        return ProfileOut(
            id=1,
            cv_filename=None,
            has_cv=False,
            has_profile=False,
            has_resume_file=RESUME_PATH.is_file(),
            updated_at=None,
        )
    return ProfileOut(
        id=p.id,
        cv_filename=p.cv_filename,
        has_cv=bool(p.cv_text),
        has_profile=bool(p.profile_markdown),
        has_resume_file=RESUME_PATH.is_file(),
        updated_at=p.updated_at,
    )


def _apply_out(p: UserProfile | None) -> ApplyProfileOut:
    row = p or UserProfile(id=1)
    profile = build_apply_profile(row.cv_text, row.profile_markdown)
    return ApplyProfileOut(
        full_name=profile.full_name,
        first_name=profile.first_name,
        last_name=profile.last_name,
        email=profile.email,
        phone=profile.phone,
        location=profile.location,
        linkedin_url=profile.linkedin_url,
        github_url=profile.github_url,
        portfolio_url=profile.portfolio_url,
        has_resume_file=RESUME_PATH.is_file(),
    )


@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    return _to_out(db.get(UserProfile, 1))


@router.get("/apply", response_model=ApplyProfileOut)
def get_apply_profile(db: Session = Depends(get_db)):
    return _apply_out(db.get(UserProfile, 1))


@router.get("/cv")
def get_resume_pdf():
    if not RESUME_PATH.is_file():
        raise HTTPException(404, "Resume file not uploaded")
    return FileResponse(RESUME_PATH, media_type="application/pdf", filename="resume.pdf")


MIN_PDF_TEXT_CHARS = 200


def _read_pdf_text(data: bytes, label: str) -> str:
    try:
        text = extract_pdf_text(data).strip()
    except Exception as e:
        raise HTTPException(400, f"Could not read the {label} PDF: {e}") from e
    if len(text) < MIN_PDF_TEXT_CHARS:
        raise HTTPException(
            400,
            f"No usable text found in the {label} PDF. Scanned or image-only PDFs are not supported; "
            "export a text-based PDF. Your previous data was kept.",
        )
    return text


@router.post("", response_model=ProfileOut)
async def upload_profile(
    db: Session = Depends(get_db),
    cv: UploadFile | None = File(None),
    profile: UploadFile | None = File(None),
):
    cv_data: bytes | None = None
    cv_text: str | None = None
    if cv and cv.filename:
        cv_data = await cv.read()
        cv_text = _read_pdf_text(cv_data, "CV")

    profile_text: str | None = None
    if profile and profile.filename:
        profile_text = _read_pdf_text(await profile.read(), "profile")

    row = db.get(UserProfile, 1)
    if not row:
        row = UserProfile(id=1)
        db.add(row)

    if cv_data is not None:
        row.cv_text = cv_text
        row.cv_filename = cv.filename
        RESUME_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESUME_PATH.write_bytes(cv_data)

    if profile_text is not None:
        row.profile_markdown = profile_text

    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _to_out(row)
