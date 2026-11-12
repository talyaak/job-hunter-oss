# Troubleshooting

Start with `npm run doctor` (or `npm run doctor:full` while the app runs). Every failing check prints a fix.

| Symptom | Cause / fix |
|---|---|
| "Private access" lock screen on localhost | `LOCAL_TRUST=false`, or you opened the app through a non-local hostname. Use `http://localhost:5173` or paste the token from `.env`. |
| `401` from the API in scripts | send `Authorization: Bearer <ACCESS_TOKEN>`. Local requests without proxy headers skip it. |
| Tunnel URL "can't be reached" right after start | DNS for the new `trycloudflare.com` name can lag (and negative-cache locally). Wait a minute, flush DNS (`ipconfig /flushdns` on Windows), or test from your phone on mobile data. |
| `cloudflared not found` | install it (`winget install Cloudflare.cloudflared`, `brew install cloudflared`, or the Linux package) |
| `[tunnel] ACCESS_TOKEN is empty` | run `npm run setup -- --skip-install` |
| Sync: "Upload your CV before syncing" | upload a text-based PDF in Setup & settings |
| Gemini 429 / quota | wait, lower `INGESTION_POOL_*`, or use a key with billing. The pipeline logs the rejected job with the error. |
| Gemini 404 "no longer available" | Google retired the pinned model: `npm run doctor -- --models`, then set `GEMINI_MODEL` (the default `gemini-flash-latest` alias avoids this) |
| Few/no leads | `GET /api/insights/summary` or the `tips` skill; usually threshold or filters |
| LinkedIn returns nothing / 429 | you are rate limited: reduce pools, wait, refresh the cookie; see [LINKEDIN.md](LINKEDIN.md) |
| `ModuleNotFoundError: jobspy` | `pip install -e backend` (the venv from `npm run setup`) |
| Port already in use | `npm run kill-ports` (dev already does this at start) |
| Windows: "DLL load failed ... Application Control policy" | a security policy blocks freshly installed compiled packages (numpy, pandas, SQLAlchemy). Allow-list `backend/.venv` with your IT/security tool, or reinstall versions your policy already trusts |
| Migrations out of date | `cd backend && python -m alembic upgrade head` |

## Docker (optional)

```bash
cp .env.example .env        # or `npm run setup` once
docker compose up --build   # app on http://localhost:5173/?t=<ACCESS_TOKEN>
```

Inside containers requests do not come from loopback, so the access token is always required (even on localhost).
Ports are published on `127.0.0.1` only. Run onboarding with
`docker compose run --rm api python -m app.onboard`. For the phone tunnel, run `npm run tunnel` on the host.
