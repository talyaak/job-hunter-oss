# Job Hunter

Job Hunter collects job postings from LinkedIn and Indeed, scores each one against your CV with Google's Gemini API,
and shows only the good matches in a web dashboard on your own computer. You set what you are looking for (titles,
location, words to reject, minimum score) and it re-runs a few times a day. Your CV and settings stay on your machine;
only job text and CV excerpts are sent to Gemini for scoring.

You need a Gemini API key. A few dollars of API credit is enough to get it running and see whether it fits your search
(see [Cost](#cost)).

**Also included:** phone push alerts (ntfy), a token-protected tunnel to open the dashboard from your phone, a Chrome
extension that fills application forms, and agent skills (`onboard`, `doctor`, `tips`, `calibrate`, `cv-optimizer`) for
setup, tuning and CV tailoring.

## How it works

```
LinkedIn / Indeed / Google ATS
        |  scrape (JobSpy, Playwright, SerpAPI)
        v
  location -> hard rejects -> dedupe -> embedding filter -> LLM pre-filter -> similar examples (RAG)
        |                                   (shadow mode by default)
        v
  Gemini scores 5 dimensions -> weighted score computed in code -> threshold -> lead + ntfy push
```

## Cost

The Gemini API is the only paid part, and the system is built to use little of it. Rules and de-duplication run first
(free), the AI pre-filters start in shadow mode, text sent to the model is truncated, embeddings are cached by content
hash, and sweeps are capped. Only jobs that survive the cheap steps reach the scoring call.

Measured on a real call (one-page CV, ~3,000-character job description, `gemini-flash-latest`): about **2,500 input
tokens and ~1,900 output tokens (including the model's reasoning), ~4,400 in total per scored job.** In a small live sweep
11 postings were scraped and 7 were scored by the model; the rest were dropped by free rules or duplicates.

- **Rule of thumb:** `jobs scored x ~4,400 tokens`. A few hundred scored jobs per week is about a million tokens. Check
  Google's current price for the model you choose at https://ai.google.dev/gemini-api/docs/pricing and multiply.
- **Try it first:** the free tier of AI Studio can be enough to try it, but has rate limits; a few dollars of prepaid
  credit removes that friction and covers a long trial. Free-tier prompts may be used by Google to improve its products,
  so read Google's terms before sending a CV you consider sensitive ([docs/PRIVACY.md](docs/PRIVACY.md)).
- **Spend less:** lower `INGESTION_POOL_SIZE` / `INGESTION_POOL_COUNT`, tighten titles and blocked words, raise the
  threshold only after reading the Rejected tab, or pick a `-lite` model with `GEMINI_MODEL` (`npm run doctor -- --models`
  lists what your key can use).

## Quick start

Requirements: Node 18+, Python 3.11+, a [Gemini API key](https://aistudio.google.com/apikey) (Windows: see [docs/WINDOWS.md](docs/WINDOWS.md)).

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
