# Configuration

Two layers:

1. **Preferences** (in the app: Setup & settings, or `GET/PUT /api/preferences`): what you search for and how jobs are judged.
2. **`.env`** (secrets and machine options): see `.env.example`, every key is commented.

## Preferences

| Field | Meaning | Default |
|---|---|---|
| `target_titles` | titles searched, joined as `("A" OR "B")` | `Software Engineer` |
| `search_location`, `country` | location sent to LinkedIn/Indeed; Indeed country | `Remote`, empty |
| `hours_old` | max age of postings (overrides `JOBSPY_HOURS_OLD`) | unset |
| `allowed_location_signals` / `blocked_location_markers` | keep jobs mentioning an allowed signal; reject ones mentioning a blocked marker. Both empty = no location filter | empty |
| `blocked_title_keywords`, `blocked_description_keywords`, `blocked_companies` | hard rejects (whole words/phrases, case-insensitive) | empty |
| `reject_contract_roles` | reject contractor/freelance/fixed-term signals | true |
| `score_threshold`, `high_score_threshold` | keep leads from this score; highlight from this score | 80, 90 |
| `weights` | the five dimension weights (normalised to sum 1) | 0.50/0.15/0.15/0.10/0.10 |
| `ignore_education_deal_breakers`, `ignore_tenure_deal_breakers` | a missing degree / years shortfall lowers the score instead of being a deal-breaker | true, true |
| `candidate_notes` | plain-language wants and avoids injected into the scoring prompt | empty |
| `extra_scoring_rules` | extra rules, one per line | empty |
| `cron_hours`, `timezone` | sweep hours (0-23) and IANA timezone | 10, 15, 19; `CRON_TIMEZONE` or UTC |

Prompts: edit `backend/app/llm/prompts/score.md`, `prefilter.md`, `cover_letter.md` (placeholders look like `[[CV]]`).

## `.env` highlights

| Key | Notes |
|---|---|
| `GEMINI_API_KEY`, `GEMINI_MODEL`, `EMBEDDING_MODEL` | required key; models are configurable (default `gemini-flash-latest`; `npm run doctor -- --models` lists what your key can call) |
| `EMBEDDING_FILTER_ENABLED` + `EMBEDDING_SHADOW_MODE` | keep shadow mode on until the doctor/insights show the filter would not drop good jobs |
| `GEMMA_FILTER_ENABLED` + `GEMMA_SHADOW_MODE` | same for the yes/no pre-filter |
| `LINKEDIN_ENABLED`, `LINKEDIN_COOKIE_STRING`, `LINKEDIN_ENRICH_MAX`, `LINKEDIN_ENRICH_DELAY_SECONDS` | see [LINKEDIN.md](LINKEDIN.md) |
| `GOOGLE_PLAYWRIGHT_ENABLED` | needs `pip install -e "backend[playwright]"` and `playwright install chromium` |
| `NTFY_TOPIC`, `NTFY_SERVER` | long random topic; self-hosted ntfy supported |
| `ACCESS_TOKEN`, `LOCAL_TRUST`, `TUNNEL_NOTIFY_MODE` | see [TUNNEL.md](TUNNEL.md) |
| `API_HOST`, `API_PORT`, `FRONTEND_PORT`, `CORS_ORIGINS` | keep `API_HOST=127.0.0.1` |
| `INGESTION_ENABLED` | `false` on a second backend sharing the DB |
| `APPLY_*` | overrides for extension autofill (otherwise parsed from your CV) |
