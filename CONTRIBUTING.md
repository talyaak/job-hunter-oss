# Contributing

Thanks for helping! Quick rules:

1. `npm run setup -- --skip-install` after pulling, then `npm test` and `npm run build`.
2. Keep behaviour configurable: new user-facing options belong in `app/preferences.py` (+ the setup panel), secrets and
   machine options in `app/config.py` and `.env.example`.
3. **No personal data** in code, tests, fixtures or docs. Use synthetic personas (e.g. "Alex Morgan"). A test scans the
   tree for known leaks, and CI runs gitleaks.
4. Every new API route must go through the access gate (it does by default under `/api`) and appear in the doctor's
   route sweep (`backend/app/doctor_cli.py`) when it is a safe GET.
5. LLM code goes through `app/llm/client.py`; prompts live in `app/llm/prompts/*.md`; scores are computed in code.
6. Add tests next to the code you change. Backend: `pytest` in `backend/tests`. LLM calls are stubbed.
7. Keep the Windows/macOS/Linux scripts working (`scripts/*.mjs`, plain Node, no shell-isms).

## Layout

`backend/app` FastAPI app, pipeline and filters · `frontend/src` Vue app · `extension` Chrome extension ·
`scripts` cross-platform dev scripts · `.claude/skills` agent skills · `docs` documentation.
