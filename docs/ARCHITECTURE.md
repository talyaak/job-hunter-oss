# Architecture

```
frontend (Vue 3 + Vite, :5173) --/api (proxy, incl. WebSocket)--> backend (FastAPI, 127.0.0.1:8000) --> SQLite (WAL)
        ^                                                              |-- scheduler (APScheduler, hours from preferences)
cloudflared quick tunnel -> :5173                                      |-- pipeline: sources -> filters -> LLM -> leads
Chrome extension -> backend (token for non-local URLs)                 |-- ntfy push (new leads, tunnel link)
```

## Backend (`backend/app`)

| Area | Files | Notes |
|---|---|---|
| App + gate | `main.py`, `security.py`, `api/auth.py` | pure-ASGI access middleware covers HTTP and WebSocket |
| Config | `config.py`, `envfile.py` | secrets/infra from `.env`; safe `.env` writer used by onboarding |
| Preferences | `preferences.py`, `api/preferences.py`, table `user_preferences` | one JSON document with neutral defaults |
| Onboarding / health | `onboard.py`, `api/onboarding.py`, `doctor.py`, `doctor_cli.py`, `api/health.py` | same checks in CLI, API and UI |
| Sources | `ingestion/jobspy_source.py` (LinkedIn, Indeed), `google_ats.py`, `google_playwright.py`, `linkedin_auth.py`, `linkedin_search.py` | queries built from preferences |
| Filters | `filter/location_reject.py`, `hard_reject.py`, `dedupe.py`, `embeddings.py`, `gemma_filter.py` | all configurable, shadow modes for the AI filters |
| LLM | `llm/client.py`, `llm/prompts/*.md`, `filter/gemini_scorer.py`, `filter/evaluation.py`, `filter/cover_letter.py` | google-genai, retries, JSON mode; templates are editable Markdown |
| Pipeline | `ingestion/pipeline.py`, `filter/unscored_backlog.py` | orchestration, live status over `/api/sync/ws` |
| API | `api/leads.py`, `rejects.py`, `profile.py`, `search.py`, `sync.py`, `insights.py` | |

## Pipeline order

1. Scrape (LinkedIn/Indeed via JobSpy; optional Google ATS and SerpAPI).
2. Optional authenticated LinkedIn description fetch (capped, jittered).
3. Location filter -> hard rejects (blocked title/description words, companies, contract roles).
4. Dedupe (URL, company+title fingerprint, previous leads and rejects).
5. Embedding similarity (profile chunks vs job) and a small-model yes/no pre-filter: **shadow mode by default** (they
   only count what they would reject).
6. Retrieve similar previously scored jobs (RAG) and pass them as calibration context.
7. Gemini rates five dimensions with evidence; **code** computes the weighted score from your weights; deal-breaker
   policy is applied from preferences.
8. Score >= threshold becomes a lead (+ ntfy push); everything else is stored in Rejected with its reason.

## Scoring

Dimensions: `hard_requirements_score`, `domain_similarity_score`, `seniority_score`, `technology_score`,
`signal_score`. Default weights 0.50/0.15/0.15/0.10/0.10 (normalised if you edit them). The model never computes the
final number.

## Access gate

See [TUNNEL.md](TUNNEL.md). The gate sits in front of every `/api` route; tests in `backend/tests/test_security.py`.

## Data

SQLite at `backend/data/job_hunter.db` (gitignored) with Alembic migrations in `backend/alembic`. Tables: leads,
ingestion_runs, ingestion_rejects, job_embeddings, user_profiles, user_preferences, linkedin_search_history/filters.
Embeddings are stored as JSON vectors; retrieval loads them in batches (fine for thousands of jobs; swap the loader for
`sqlite-vec` or similar if you outgrow it).
