---
name: onboard
description: Guide a new user through first-run setup of Job Hunter (dependencies, Gemini key, CV, search preferences, optional LinkedIn cookie, ntfy, private tunnel) and finish with a health check. Use when the user just cloned the repo, says "set this up", "get me started", or the doctor reports missing setup.
---

# Onboarding

Goal: a working, private Job Hunter in a few minutes, with the user understanding each setting. Be conversational but
do the work: run the commands, read results, fix problems.

## Ask first: do they want to learn how it works?
Before doing anything, ask once, plainly: **"Do you want short explanations of how this system works as we set it up
(about 2-3 sentences per step), or should I just set it up?"** Respect the answer for the whole session; they can switch
later ("explain that" / "skip the explanations").
- **Yes:** before each step below, give the matching 2-3 sentence note (they are the same ones the CLI prints with
  `--learn`; the longer version is [docs/HOW_IT_WORKS.md](../../../docs/HOW_IT_WORKS.md), section in brackets). Then do the
  step, then ask one optional "Try it" question from that section. Keep it brief and tied to *their* data.
  Run the CLI with `npm run setup -- --learn`.
- **No:** run `npm run setup -- --no-learn` and keep chat to what is needed.
Never lecture unasked, never block progress on a quiz, and offer the long guide only once at the end.

| Step | Teach (if they said yes) |
|---|---|
| Install / `.env` | secrets vs. preferences; why there is an access token [sections 4, 8] |
| Gemini key | what the model sees and rates; the score is computed by code, not the AI [3] |
| CV | the CV is the yardstick; embeddings in one sentence [5] |
| Preferences | cheap filters before the AI, threshold, Rejected is for tuning [2, 6] |
| LinkedIn | guest vs. cookie, caps, terms risk [7] |
| ntfy / tunnel | topic is like a password; token gate [8] |
| First sweep | read Leads vs. Rejected together [1] |

## Windows first
Most users are on Windows. Check what they have and point to [docs/WINDOWS.md](../../../docs/WINDOWS.md):
native needs Node 18+, Python 3.11+, Git (one command each: `winget install OpenJS.NodeJS.LTS`, `winget install Python.Python.3.12`,
`winget install Git.Git`), optional
`cloudflared`. Explain *why* only when relevant: **WSL** (a real Linux VM inside Windows) is optional and helps on
managed laptops that block compiled Python packages or if they like Linux tooling; **Docker** is optional and gives an
isolated, reproducible install but needs Docker Desktop (WSL2 backend) and always requires the access token. Recommend
native unless they hit a policy block or prefer isolation.

## Rules
- **Never print or echo secret values** (Gemini key, `li_at` cookie, `ACCESS_TOKEN`, ntfy topic). Show them masked
  (`****1234`). Do not put secrets in commit messages, logs or chat summaries.
- Ask the user to type secrets themselves into the interactive setup or the app's setup panel when possible; if they
  paste one to you, write it to `.env` only through `npm run setup -- --gemini-key ...` style flags or the
  `/api/onboarding/env` endpoint, then never repeat it.
- Do not log in to any account for the user and do not solve CAPTCHAs. LinkedIn cookie capture is a manual step.
- Be honest about LinkedIn: automated access may violate its terms; keep volumes low (see `docs/LINKEDIN.md`).

## Steps

1. **Prerequisites**: check `node -v` (>= 18) and `python --version` (>= 3.11). If missing, give the winget commands (Windows)
   or package-manager hint and stop. If `python` opens the Microsoft Store, see the Windows traps in `docs/WINDOWS.md`.
2. **Install and migrate**: `npm run setup` does the virtualenv, `pip install -e backend`, `npm install`, `alembic upgrade
   head`, then the interactive questions. For a non-interactive run pass flags, e.g.
   `npm run setup -- --yes --gemini-key <key> --cv <path.pdf> --titles "Backend Engineer, SRE" --location "Berlin"`.
3. **Gemini key**: send them to https://aistudio.google.com/apikey. Tell them the cost expectation: a few dollars of API credit is
   enough to try the system; roughly 4,400 tokens per scored job (README, Cost). The free tier works but is rate limited. The setup validates it with a 1-token call. A 429
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
