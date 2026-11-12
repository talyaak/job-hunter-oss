"""``python -m app.onboard`` : interactive first-run setup (also exposed as ``npm run setup``).

Idempotent: re-running keeps existing values as defaults. Steps: .env + access token, Gemini key,
CV, search preferences, optional LinkedIn cookie and ntfy topic, then a doctor run.
"""

from __future__ import annotations

import argparse
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path

from app.config import ENV_FILE, REPO_ROOT, settings
from app.db.models import UserProfile
from app.db.session import Base, SessionLocal, engine
from app.envfile import ensure_access_token, mask, update_env
from app.preferences import get_preferences, save_preferences


# Short "how it works" notes shown before each step when the learner opted in (see docs/HOW_IT_WORKS.md).
LEARN: dict[str, str] = {
    "env": (
        "Two kinds of settings: secrets live in the local .env file (never committed or shown in full); what you want\n"
        "(titles, location, threshold...) lives in the app as Preferences. The ACCESS_TOKEN created now protects the\n"
        "app whenever it is reached through a public tunnel, so a leaked URL alone shows nothing."
    ),
    "gemini": (
        "Gemini reads each job together with your CV and rates five things 0-100 (requirements, domain, seniority,\n"
        "technology, signals). Your key stays in .env; job and CV text are sent to Google only to be scored."
    ),
    "cv": (
        "Your CV is the yardstick. Its text is stored locally and compared with every job. It is also turned into\n"
        "'embeddings' (numbers that capture meaning) so very different jobs can be skipped cheaply. Text-based PDFs only."
    ),
    "preferences": (
        "Cheap rules run first (blocked title words, location, duplicates) so the AI only reads promising jobs. The\n"
        "threshold decides what becomes a lead; everything else lands in Rejected with its reason so you can tune.\n"
        "The final percentage is computed by code from your weights, not by the AI."
    ),
    "linkedin": (
        "Without login LinkedIn only shows short job snippets. A li_at cookie (copied by you from your own browser)\n"
        "lets the app read full descriptions, which improves scoring. It is capped and spaced out to be polite."
    ),
    "ntfy": (
        "ntfy.sh sends a push to your phone for new leads and for your private tunnel link. The topic name acts like a\n"
        "password, so it is random and long: anyone who knows it can read your alerts."
    ),
    "doctor": (
        "The doctor checks config, database, keys and (with --probe/--sweep) every endpoint, and prints a fix hint per\n"
        "problem. Run it whenever something feels off."
    ),
}

LEARN_MODE = False


def explain(key: str) -> None:
    if LEARN_MODE and key in LEARN:
        print("  [how it works] " + LEARN[key].replace("\n", "\n                 "))


def ask(prompt: str, default: str = "", secret: bool = False, assume_yes: bool = False) -> str:
    if assume_yes:
        return default
    suffix = f" [{mask(default) if secret and default else default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default
    return value or default


def ask_yes(prompt: str, default: bool = True, assume_yes: bool = False) -> bool:
    if assume_yes:
        return default
    answer = ask(f"{prompt} ({'Y/n' if default else 'y/N'})", "").lower()
    if not answer:
        return default
    return answer.startswith("y")


def split_csv(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


def step_env() -> None:
    example = REPO_ROOT / ".env.example"
    if not ENV_FILE.exists() and example.exists():
        shutil.copy(example, ENV_FILE)
        print(f"Created {ENV_FILE.name} from .env.example")
    explain("env")
    token = ensure_access_token()
    print(f"Access token ready ({mask(token)}). The tunnel link will include it; never share that link.")


def step_gemini(assume_yes: bool, key_arg: str | None) -> None:
    print("\n== Gemini API key ==")
    explain("gemini")
    print("Create a free key at https://aistudio.google.com/apikey")
    key = key_arg or ask("GEMINI_API_KEY", settings.gemini_api_key, secret=True, assume_yes=assume_yes)
    if not key:
        print("Skipped (scoring will not work until you add a key).")
        return
    update_env({"GEMINI_API_KEY": key})
    if ask_yes("Validate the key with a tiny test call?", True, assume_yes):
        from app.llm.client import generate_text

        try:
            generate_text("Reply with the single word OK.", max_output_tokens=16)
            print("Gemini key works.")
        except Exception as exc:  # noqa: BLE001
            print(f"Validation failed: {str(exc)[:200]}\nFix the key and re-run `npm run setup`.")


def step_cv(assume_yes: bool, cv_arg: str | None) -> None:
    print("\n== Your CV ==")
    explain("cv")
    with SessionLocal() as db:
        existing = db.get(UserProfile, 1)
        default = ""
        if existing and existing.cv_text:
            print(f"A CV is already stored ({existing.cv_filename or 'unnamed'}). Press Enter to keep it.")
        raw = cv_arg or ask("Path to your CV (text-based PDF)", default, assume_yes=assume_yes)
        if not raw:
            return
        path = Path(raw.strip().strip('"')).expanduser()
        if not path.is_file():
            print(f"File not found: {path}")
            return
        from app.api.profile import MIN_PDF_TEXT_CHARS, RESUME_PATH
        from app.filter.cv_parser import extract_pdf_text

        data = path.read_bytes()
        text = extract_pdf_text(data).strip()
        if len(text) < MIN_PDF_TEXT_CHARS:
            print("No usable text in that PDF (scanned/image-only PDFs are not supported).")
            return
        row = existing or UserProfile(id=1)
        row.cv_text = text
        row.cv_filename = path.name
        row.updated_at = datetime.utcnow()
        if not existing:
            db.add(row)
        db.commit()
        RESUME_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESUME_PATH.write_bytes(data)
        print(f"Stored CV text ({len(text)} chars).")


def step_preferences(assume_yes: bool, args: argparse.Namespace) -> None:
    print("\n== Search preferences ==")
    explain("preferences")
    with SessionLocal() as db:
        prefs = get_preferences(db)
        titles = args.titles or ask("Job titles to search (comma separated)", ", ".join(prefs.target_titles), assume_yes=assume_yes)
        prefs.target_titles = split_csv(titles) or prefs.target_titles
        prefs.search_location = args.location or ask("Location (e.g. 'Berlin, Germany' or 'Remote')", prefs.search_location, assume_yes=assume_yes)
        prefs.country = args.country if args.country is not None else ask("Country for Indeed (e.g. 'USA', blank = default)", prefs.country, assume_yes=assume_yes)
        blocked = ask("Title words to always reject (e.g. Manager, Intern, QA)", ", ".join(prefs.blocked_title_keywords), assume_yes=assume_yes)
        prefs.blocked_title_keywords = split_csv(blocked)
        thr = ask("Minimum match score to keep a lead (0-100)", str(prefs.score_threshold), assume_yes=assume_yes)
        if thr.isdigit():
            prefs.score_threshold = max(0, min(100, int(thr)))
        prefs.candidate_notes = ask("Anything the scorer should know (wants/avoids), one line", prefs.candidate_notes, assume_yes=assume_yes)
        hours = ask("Hours to run the sweep (comma separated, 0-23)", ", ".join(map(str, prefs.cron_hours)), assume_yes=assume_yes)
        parsed = [int(h) for h in split_csv(hours) if h.isdigit()]
        prefs.cron_hours = parsed or prefs.cron_hours
        prefs.timezone = ask("Timezone (IANA, e.g. Europe/Berlin)", prefs.timezone or settings.cron_timezone, assume_yes=assume_yes)
        prefs.onboarding_complete = True
        save_preferences(db, prefs)
        print("Preferences saved. You can fine-tune them in the app or let the `tips` skill suggest changes.")


def step_linkedin(assume_yes: bool, cookie_arg: str | None) -> None:
    print("\n== LinkedIn (optional) ==")
    explain("linkedin")
    print("Guest scraping works without login. A li_at cookie unlocks full job descriptions (see docs/LINKEDIN.md).")
    print("Heads-up: automated access may violate LinkedIn's terms; keep volumes low and use at your own risk.")
    if not (cookie_arg or ask_yes("Add your li_at cookie now?", False, assume_yes)):
        return
    cookie = cookie_arg or ask("li_at cookie value", settings.linkedin_cookie_string, secret=True)
    if cookie:
        update_env({"LINKEDIN_COOKIE_STRING": cookie})
        from app.ingestion.linkedin_auth import check_linkedin_cookie

        ok, detail = check_linkedin_cookie()
        print(("OK: " if ok else "Warning: ") + detail)


def step_ntfy(assume_yes: bool) -> None:
    print("\n== Push notifications (optional) ==")
    explain("ntfy")
    print("ntfy.sh pushes new leads and your private tunnel link to your phone. Install the ntfy app and subscribe to the topic.")
    if settings.ntfy_topic:
        print(f"Topic already set ({mask(settings.ntfy_topic)}).")
        return
    if ask_yes("Generate a private random topic?", True, assume_yes):
        topic = "jh-" + secrets.token_urlsafe(18).replace("_", "x").replace("-", "y")
        update_env({"NTFY_TOPIC": topic})
        print(f"Subscribe to this topic in the ntfy app: {topic}\n(anyone who knows it can read your alerts; do not share it)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="onboard")
    ap.add_argument("--yes", action="store_true", help="accept defaults / non-interactive")
    ap.add_argument("--gemini-key")
    ap.add_argument("--cv")
    ap.add_argument("--titles")
    ap.add_argument("--location")
    ap.add_argument("--country")
    ap.add_argument("--linkedin-cookie")
    ap.add_argument("--skip-doctor", action="store_true")
    learn = ap.add_mutually_exclusive_group()
    learn.add_argument("--learn", action="store_true", help="show short 'how it works' notes at each step")
    learn.add_argument("--no-learn", action="store_true", help="do not ask about or show the notes")
    args = ap.parse_args(argv)

    global LEARN_MODE
    if args.learn:
        LEARN_MODE = True
    elif args.no_learn or args.yes:
        LEARN_MODE = False
    else:
        LEARN_MODE = ask_yes("Would you like short 'how it works' notes at each step? (about 3 lines each)", True)

    print("Job Hunter setup\n----------------")
    Base.metadata.create_all(bind=engine)
    step_env()
    step_gemini(args.yes, args.gemini_key)
    step_cv(args.yes, args.cv)
    step_preferences(args.yes, args)
    step_linkedin(args.yes, args.linkedin_cookie)
    step_ntfy(args.yes)

    if not args.skip_doctor:
        print("\n== Health check ==")
        explain("doctor")
        from app.doctor_cli import main as doctor_main

        doctor_main([])
    print("\nDone. Start everything with `npm run dev` (or `npm run dev:tunnel` for phone access).")
    if LEARN_MODE:
        print("Want the longer version? Read docs/HOW_IT_WORKS.md, or ask your assistant to walk you through it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
