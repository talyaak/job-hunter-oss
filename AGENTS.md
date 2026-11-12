# Guide for LLM coding assistants (Claude Code, Cursor, Codex, ...)

You are helping a person set up and run **their own copy** of Job Hunter. Read this file first, then the skill that
matches what they ask. Everything here is written so you can act without guessing.

## What this project is
A self-hosted job sweep: scrape LinkedIn/Indeed -> filter -> Gemini scores each job against the person's CV -> leads
in a local dashboard, optional phone push (ntfy) and a private tunnel. All settings are per person; nothing in the code
is specific to anyone. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Hard rules
1. **Never print, log, paste or commit secrets**: `GEMINI_API_KEY`, `LINKEDIN_COOKIE_STRING` (`li_at`), `ACCESS_TOKEN`,
   the ntfy topic, tunnel links containing `?t=`. Show them masked (`****1234`). Do not put them in commit messages,
   issues or summaries.
2. **Never read the user's CV, `.env` or `backend/data/` into third-party tools** or share them outside this machine.
   The CV is sent only to the user's configured Gemini key (see [docs/PRIVACY.md](docs/PRIVACY.md)).
3. **Do not log in to accounts, solve CAPTCHAs, or fetch cookies for the user.** The LinkedIn cookie is copied by the
   user from their own browser ([docs/LINKEDIN.md](docs/LINKEDIN.md)). Tell them LinkedIn automation may violate its terms.
4. **Ask before outward-facing actions**: pushing to a remote, making a repo public, opening a tunnel, sending a push
   notification, creating accounts. The tunnel is safe by design (token-gated) but the user decides when it is on.
5. Do not weaken the access gate (`backend/app/security.py`) or bind the API to a non-loopback address unless the user
   explicitly asks and understands the exposure.
6. Never invent facts for the user's CV. Use the `cv-optimizer` skill, which marks unverified claims `[TO CONFIRM]`.

## Which skill to use
| The user says... | Use |
|---|---|
| "set this up", "get started", just cloned | `.claude/skills/onboard` |
| "is it working", errors, before a tunnel | `.claude/skills/doctor` |
| "why so few/many leads", "improve results" | `.claude/skills/tips` |
| "the scores feel off", after a week of use | `.claude/skills/calibrate` |
| CV feedback, "should I apply", rewrite my CV | `.claude/skills/cv-optimizer` |
Tool-agnostic fallback: open the matching `SKILL.md` and follow it literally.

## Fast path to a working install (what you will run)
```bash
npm run setup          # venv + deps + migrations + interactive onboarding (asks the user for key/CV/preferences)
npm run doctor         # no network; should show no FAIL except missing key/CV before onboarding finishes
npm run dev            # http://localhost:5173
npm run doctor:full    # with the app running: Gemini/LinkedIn/ntfy probes + every endpoint + WebSocket
```
Non-interactive: `npm run setup -- --yes --gemini-key <key> --cv <file.pdf> --titles "A, B" --location "City"`
(ask the user to type the key themselves when possible; never echo it back).

## Curating the experience for this person
After the first sweep, help them make it theirs. Work from data, change one thing at a time, and always show the
diff before applying:
1. Open **Setup & settings** or `GET /api/preferences`; confirm titles, location, blocked words, threshold, hours.
2. Look at **Rejected** (and `GET /api/insights/summary`). Use `tips` to propose changes; apply only what they approve.
3. After ~20 rated leads run `calibrate` for the threshold and weights.
4. Put their wants/avoids into `candidate_notes` in plain language; this steers the scorer more than any keyword.
5. Offer `cv-optimizer` for specific leads they care about.
6. Keep a short note for them of what you changed and why (preferences are in the app, not in git).

## When something fails
Run `npm run doctor` and follow the `->` hint on the first FAIL; fix in the order in `.claude/skills/doctor/SKILL.md`.
Known environment gotchas are in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) (new tunnel DNS lag, Gemini model
retirement `npm run doctor -- --models`, Windows Application Control blocking compiled packages, LinkedIn markup changes).

## Working on the code
See [CONTRIBUTING.md](CONTRIBUTING.md). Tests: `npm test`. Frontend: `npm run build`. No personal data in code, tests or docs;
LLM calls go through `backend/app/llm/client.py`; prompts are Markdown in `backend/app/llm/prompts/`; scores are computed in code.

## Independent validation checklist (to run on a machine/VM other than the author's)
This is the part the author could not run on a second physical machine. If the user wants confidence, do this on a
fresh machine or VM and report results (pass/fail + the exact failing line) in an issue, without secrets:
1. Fresh clone; only the README: `npm run setup`, `npm test` (expect all green), `npm run dev`.
2. `npm run doctor:full` (needs a Gemini key): every route PASS, `websocket` PASS.
3. Run one small sweep from the UI; confirm leads or sensible rejects appear.
4. `npm run dev:tunnel` (needs `cloudflared`): from a phone on mobile data, open the pushed link; unlock works; then
   `npm run doctor -- --sweep --tunnel` shows 401 without token and 200 with it.
5. Human skill try-outs: see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md#try-the-skills-and-tell-us-what-happened).
