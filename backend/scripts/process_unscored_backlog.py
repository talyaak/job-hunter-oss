"""Process awaiting-score backlog. Run from backend/: python scripts/process_unscored_backlog.py [--mode auto|score|dismiss] [--limit N]"""

import argparse

from app.db.session import SessionLocal

from app.filter.unscored_backlog import process_unscored_backlog


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="auto", choices=("auto", "score", "dismiss"))
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    with SessionLocal() as db:
        stats = process_unscored_backlog(db, mode=args.mode, limit=args.limit)
        print(stats)


if __name__ == "__main__":
    main()
