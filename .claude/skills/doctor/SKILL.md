---
name: doctor
description: Health-check Job Hunter end to end (config, database and migrations, Gemini, LinkedIn cookie, ntfy, scheduler, every API endpoint, the sync WebSocket and the tunnel access gate) and fix what fails. Use when something is broken, after setup or upgrades, before opening a tunnel, or when the user says "check everything", "is it working", "health check", "why no leads".
---

# Doctor

Run diagnostics, interpret them, fix problems, and re-run until green. Never print secret values.

## Commands (from the repo root)

| Command | What it checks | Needs server |
|---|---|---|
| `npm run doctor` | config, DB + migrations, access token, bind address, preferences, CV, Gemini key present, LinkedIn/ntfy configured, deps | no |
| `npm run doctor -- --probe` | the above plus real calls to Gemini (generate + embed), the LinkedIn cookie and a test ntfy push | no |
| `npm run doctor:full` | probe + a request to every API route + the `/api/sync/ws` handshake | yes (`npm run dev`) |
| `npm run doctor -- --sweep --tunnel` | route sweep + verifies through the public tunnel URL that an unauthenticated request gets 401 and the token works | yes + tunnel |
| `npm run doctor -- --json` | machine-readable output for CI | no |

The same checks are available in the UI (Setup & settings -> Health check) and as `GET /api/health/deep?probe=true`.
`GET /api/health/live` is the only unauthenticated endpoint.

## Procedure
1. Run `npm run doctor`. Read every WARN/FAIL and its `->` hint.
2. If the server is up, run `npm run doctor:full`; if a tunnel is up, add `--tunnel`.
3. Fix in this order (each often explains the next):
   1. `database` / `migrations`: `cd backend && python -m alembic upgrade head`; check `DATABASE_URL`.
   2. `access_token` FAIL: run `npm run setup -- --skip-install` (generates one). Never open a tunnel without it.
   3. `gemini_*`: wrong key (re-run setup), model name (`GEMINI_MODEL`), or quota (429: wait or enable billing).
   4. `profile`: upload a text-based PDF CV.
   5. `preferences`: complete onboarding (titles, location, threshold).
   6. `linkedin`: cookie expired -> copy a fresh `li_at` (see `docs/LINKEDIN.md`); not required for guest scraping.
   7. `route ...` 401: token mismatch between `.env` and the client; 500: read the backend log for the traceback.
   8. `tunnel gate (no token)` FAIL: **stop the tunnel immediately**, check `ACCESS_TOKEN` is non-empty and the backend
      was restarted, then re-test.
4. Re-run until the overall result is PASS (WARN is acceptable only when the user explains it is intentional).

## "Why no leads?" triage
Use `GET /api/insights/summary` (or the `tips` skill):
- many rejects at `hard_title` or `location` -> filters too broad/aggressive;
- many `llm_score` rejects just under the threshold -> threshold too high or preferences too vague;
- raw_count near zero -> search terms/location too narrow, or LinkedIn blocking (check logs, lower volumes);
- `sync` errors "Upload your CV" -> profile missing.

## Reporting
Summarise as a table (check, status, action taken) and list anything left for the user to do manually.
