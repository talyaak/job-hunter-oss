# Job Hunter

A self-hosted job sweep that **you run on your own machine**. It scrapes LinkedIn and Indeed (and optionally Google ATS
boards), filters the noise, scores every job against *your* CV with Gemini, and shows only the leads worth your time.
New leads can be pushed to your phone, and a private tunnel lets you open the dashboard anywhere, protected by a token
only you have.

- **Your data stays with you**: SQLite file, `.env` secrets and CV never leave your machine except the job and CV text
  sent to Gemini for scoring (see [docs/PRIVACY.md](docs/PRIVACY.md)).
- **Made for your search**: titles, locations, blocklists, thresholds, weights and schedule are settings, not code.
- **AI where it helps**: embeddings pre-filter and retrieve your past decisions as calibration examples (RAG), an LLM
  scores five dimensions, and **the final score is computed in code** from your weights.
- **Agent skills included** (`.claude/skills/`): `onboard`, `doctor`, `tips`, `calibrate` and `cv-optimizer`.

```
LinkedIn / Indeed / Google ATS
        |  scrape (JobSpy, Playwright, SerpAPI)
        v
  location -> hard rejects -> dedupe -> embedding filter -> LLM pre-filter -> similar examples (RAG)
        |                                   (shadow mode by default)
        v
  Gemini scores 5 dimensions -> weighted score computed in code -> threshold -> lead + ntfy push
```

## Quick start

Requirements: Node 18+, Python 3.11+, a free [Gemini API key](https://aistudio.google.com/apikey).

```bash
git clone <your-fork-or-this-repo> job-hunter
cd job-hunter
npm run setup      # venv + deps + migrations + interactive onboarding (key, CV, preferences)
npm run dev        # API on 127.0.0.1:8000, app on http://localhost:5173
```

Open http://localhost:5173, press **Sync**, then look at **Leads** and **Rejected** (the Rejected tab is how you tune).
The first launch also opens a setup panel in the app if anything is missing.

### Phone access through a private tunnel

```bash
# one-time: install cloudflared (winget install Cloudflare.cloudflared | brew install cloudflared)
npm run dev:tunnel
```

The terminal prints (and ntfy pushes, if configured) a link like `https://xyz.trycloudflare.com/?t=<token>`. The app
swaps the token for an HttpOnly cookie and removes it from the address bar. Without the token, every API call and the
sync WebSocket get `401`. Details and alternatives: [docs/TUNNEL.md](docs/TUNNEL.md).

### Docker instead of Node/Python locally (optional)

```bash
cp .env.example .env && docker compose up --build   # http://localhost:5173/?t=<ACCESS_TOKEN from .env>
```

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#docker-optional).

### Everyday commands

| Command | Does |
|---|---|
| `npm run setup` | install + migrate + onboarding (`-- --skip-install` re-runs onboarding only) |
| `npm run dev` / `npm run dev:tunnel` | run locally / plus the private tunnel |
| `npm run doctor` / `npm run doctor:full` | health check / full check incl. every endpoint and live Gemini/LinkedIn/ntfy calls |
| `npm test` | backend tests |
| `npm run test:ntfy` | send a test push |

**New here?** [Getting started](docs/GETTING_STARTED.md) walks you through it (Windows users: [docs/WINDOWS.md](docs/WINDOWS.md); curious how it works: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)), and if you use an LLM coding assistant,
hand it [AGENTS.md](AGENTS.md): it contains the rules, the fast path and how to tailor the app to you.

## Skills (for Claude Code and compatible agents)

| Skill | Use it to |
|---|---|
| `onboard` | be walked through setup step by step |
| `doctor` | diagnose and fix anything broken, endpoint by endpoint |
| `tips` | get data-driven advice to improve lead quality and apply it to your preferences |
| `calibrate` | tune the threshold and weights by rating sample leads |
| `cv-optimizer` | score your fit for a job, tailor your CV honestly, and optionally regenerate it ([docs/CV_OPTIMIZER.md](docs/CV_OPTIMIZER.md)) |

## Chrome extension (optional)

`extension/` fills Greenhouse, Lever, Comeet and Workday application forms from your profile (never submits). Load it
via `chrome://extensions` -> Developer mode -> Load unpacked. Set the API URL and, for a non-local URL, the access token
in its popup.

## Documentation

[Getting started](docs/GETTING_STARTED.md) · [Windows](docs/WINDOWS.md) · [How it works](docs/HOW_IT_WORKS.md) · [For assistants](AGENTS.md) · [Architecture](docs/ARCHITECTURE.md) · [Configuration](docs/CONFIGURATION.md) · [Tunnel & security](docs/TUNNEL.md) ·
[LinkedIn](docs/LINKEDIN.md) · [Privacy](docs/PRIVACY.md) · [CV optimizer](docs/CV_OPTIMIZER.md) ·
[Troubleshooting](docs/TROUBLESHOOTING.md) · [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md)

## Responsible use

Scraping job boards can violate their terms of service and can get accounts or IPs restricted. Keep volumes low, do not
resell data, and use this for your own job search at your own risk. This project is not affiliated with LinkedIn,
Indeed, Google or ntfy.

## License

MIT, see [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md).
