# LinkedIn sourcing

## What it does

- **Guest scraping** through [JobSpy](https://github.com/speedyapply/JobSpy): job lists from LinkedIn's public pages, no login.
- **Optional `li_at` cookie**: lets the app fetch the full description of each LinkedIn job (guest pages are often
  truncated), which improves scoring. Only this one cookie is used; the app never needs your email or password.

## Risks (please read)

Automated access can violate LinkedIn's terms of service and may lead to rate limiting, CAPTCHAs or account
restrictions. Defaults are conservative (pools of 50, a dry-off between pools, at most `LINKEDIN_ENRICH_MAX=60`
authenticated fetches per run with jittered delays). Use at your own risk, keep volumes low, and consider a secondary
account if that matters to you. Set `LINKEDIN_ENABLED=false` to turn LinkedIn off completely.

## Getting the cookie (manual, by you)

1. Log in to linkedin.com in your browser.
2. Open DevTools -> Application (Chrome) / Storage (Firefox) -> Cookies -> `https://www.linkedin.com`.
3. Copy the **value** of `li_at`.
4. Paste it in the app (Setup & settings -> LinkedIn) or `npm run setup -- --skip-install`. It is stored in `.env` only.

The doctor validates it (`npm run doctor -- --probe`). When it expires (typically weeks), LinkedIn redirects to login
and the check fails with a hint; repeat the steps. Treat the cookie like a password: never share or commit it.

## Tuning

Search terms and location come from your preferences. `JOBSPY_HOURS_OLD`, `INGESTION_POOL_SIZE`,
`INGESTION_POOL_COUNT` and `INGESTION_POOL_DRYOFF_SECONDS` control volume. The Dashboard has an ad-hoc LinkedIn search
tab with history, "posted X hours ago" labels and one-click save/score.
