"""One-time merge of duplicate leads by job_fingerprint. Run from backend/: python scripts/cleanup_lead_dupes.py"""

from collections import defaultdict

from sqlalchemy import select
from app.db.session import SessionLocal

from app.db.models import ApplicationStatus, Lead
from app.filter.job_fingerprint import job_fingerprint

STATUS_RANK = {
    ApplicationStatus.applied: 3,
    ApplicationStatus.saved: 2,
    ApplicationStatus.hidden: 1,
}


def pick_winner(group: list[Lead]) -> Lead:
    return max(
        group,
        key=lambda l: (
            -1 if l.relevance_score is None else l.relevance_score,
            STATUS_RANK.get(l.application_status, 0),
            l.created_at,
        ),
    )


def main() -> None:
    with SessionLocal() as db:
        leads = db.scalars(select(Lead)).all()
        groups: dict[str, list[Lead]] = defaultdict(list)
        for lead in leads:
            groups[job_fingerprint(lead.company, lead.job_title)].append(lead)

        deleted = 0
        for fp, group in groups.items():
            if len(group) < 2:
                continue
            winner = pick_winner(group)
            for lead in group:
                if lead.id == winner.id:
                    continue
                print(f"delete id={lead.id} keep id={winner.id} fp={fp}")
                db.delete(lead)
                deleted += 1
        db.commit()
        print(f"Removed {deleted} duplicate lead rows")


if __name__ == "__main__":
    main()
