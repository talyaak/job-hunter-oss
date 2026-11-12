---
name: onboard
description: Guide a new user through first-run setup of Job Hunter (dependencies, Gemini key, CV, search preferences, optional LinkedIn cookie, ntfy, private tunnel) and finish with a health check. Use when the user just cloned the repo, says "set this up", "get me started", or the doctor reports missing setup.
---

# Onboarding

Goal: a working, private Job Hunter in a few minutes, with the user understanding each setting. Be conversational but
do the work: run the commands, read results, fix problems.

## Rules
- **Never print or echo secret values** (Gemini key, `li_at` cookie, `ACCESS_TOKEN`, ntfy topic). Show them masked
  (`****1234`). Do not put secrets in commit messages, logs or chat summaries.
- Ask the user to type secrets themselves into the interactive setup or the app's setup panel when possible; if they
  paste one to you, write it to `.env` only through `npm run setup -- --gemini-key ...` style flags or the
  `/api/onboarding/env` endpoint, then never repeat it.
- Do not log in to any account for the user and do not solve CAPTCHAs. LinkedIn cookie capture is a manual step.
- Be honest about LinkedIn: automated access may violate its terms; keep volumes low (see `docs/LINKEDIN.md`).

## Steps

1. **Prerequisites**: check `node -v` (>= 18) and `python --version` (>= 3.11). If missing, explain how to install and stop.
2. **Install and migrate**: `npm run setup` does the virtualenv, `pip install -e backend`, `npm install`, `alembic upgrade
   head`, then the interactive questions. For a non-interactive run pass flags, e.g.
   `npm run setup -- --yes --gemini-key <key> --cv <path.pdf> --titles "Backend Engineer, SRE" --location "Berlin"`.
3. **Gemini key**: send them to https://aistudio.google.com/apikey. The setup validates it with a 1-token call. A 429
   means quota; a 400/403 means a wrong or restricted key.
4. **CV**: a text-based PDF (scanned images are rejected). It is stored locally and its text is sent to Gemini when
   scoring. Mention `docs/PRIVACY.md`.
5. **Preferences** (explain each, suggest sensible values from the CV):
   - target titles (what to search), location, country (Indeed),
   - words to always reject (e.g. Manager, Intern),
   - score threshold (start at 75-80; lower it if too few leads, raise if too noisy),
   - free-text "wants and avoids" for the scorer, sweep hours and timezone.
6. **LinkedIn (optional)**: explain guest scraping vs. the `li_at` cookie (`docs/LINKEDIN.md`). The user copies the
   cookie from their own browser; setup validates it.
7. **Phone alerts (optional)**: generate a private ntfy topic, tell them to install the ntfy app and subscribe. Explain
   that anyone who knows the topic can read alerts.
8. **Private tunnel (optional)**: `npm run dev:tunnel`. Explain: the public URL is useless without the access token;
   the link pushed to ntfy contains it, so keep the topic private. Mention `TUNNEL_NOTIFY_MODE=url|off` for stricter modes.
9. **Verify**: run `npm run doctor`, then start `npm run dev` and `npm run doctor:full` (needs the server running).
   Fix every FAIL using the hint shown. Offer the `doctor` skill for deeper diagnosis.
10. **First sweep**: open http://localhost:5173, press Sync, and explain the pipeline stages and the Rejected tab
    (that is where tuning information lives; the `tips` skill reads it).

## Done when
`npm run doctor` shows no FAIL, preferences are saved, at least one CV is stored, and the user knows how to start
(`npm run dev`), open the phone link (`npm run dev:tunnel`) and re-run setup (`npm run setup -- --skip-install`).
