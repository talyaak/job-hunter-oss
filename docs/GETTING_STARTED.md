# Getting started (for people)

This walks you from clone to a job sweep tuned to **you**. You can do every step yourself, or open the repo in an
LLM coding assistant (Claude Code, Cursor, ...) and say "onboard me": it will read [AGENTS.md](../AGENTS.md) and the
`onboard` skill and guide you.

## 1. Prerequisites
- Node 18+ and Python 3.11+ (`node -v`, `python --version`)
- A free Gemini API key: https://aistudio.google.com/apikey
- Your CV as a **text-based PDF** (not a scan)
- Optional: `cloudflared` (phone access), the ntfy phone app (alerts), a LinkedIn `li_at` cookie ([guide](LINKEDIN.md))

## 2. Install and answer the questions
```bash
git clone <repo-url> job-hunter && cd job-hunter
npm run setup
```
It asks for: Gemini key, CV path, job titles, location, words to always reject, score threshold, sweep hours and
timezone. Press Enter to accept a default; you can change everything later in the app (**Setup & settings**).

## 3. Run it
```bash
npm run dev            # open http://localhost:5173 and press "Sync Now"
npm run doctor:full    # in another terminal: checks everything, with a fix hint per problem
```
Read the **Rejected** tab after your first sweep: it shows why jobs were dropped and is how you tune the search.

## 4. Phone access (optional)
```bash
npm run dev:tunnel
```
Open the link it prints or pushes to your ntfy topic. Without the token the public URL shows nothing. See [TUNNEL.md](TUNNEL.md).

## 5. Make it yours (curation loop)
| When | Do this |
|---|---|
| After the first sweep | Review **Rejected**; write what you want/avoid in **Setup & settings > "Tell the scorer..."** |
| Too few or too many leads | ask your assistant: "run the tips skill" |
| After ~20 leads you have judged | "run the calibrate skill" |
| Before applying to a role | "optimise my CV for this lead" (cv-optimizer skill) |
| Something broke | "run the doctor skill" or `npm run doctor` |

Mark leads Saved / Hidden / Applied consistently: those decisions are used as examples when scoring future jobs.

## Try the skills and tell us what happened
The maintainers verified the skills' procedures against live data with scripted answers, but they have not been
used by a real person yet. If you try them, please open an issue (no secrets, no CV text) with:

1. **tips**: after at least two sweeps, ask "run the tips skill". Did the numbers it quoted match what you see in the
   app? Were its proposed changes sensible? Did applying them change only what you approved?
2. **calibrate**: ask "run the calibrate skill" with at least 10 leads and some near-miss rejects. Was rating the sample
   easy? Did the suggested threshold feel right afterwards?
3. **cv-optimizer**: run it on one lead. Did it ever invent something not in your CV? (It should mark `[TO CONFIRM]`.)
4. **onboard**: did a fresh clone get you to a passing `npm run doctor` in under ~15 minutes? Where did you get stuck?

## Privacy in one paragraph
Your CV and `.env` stay on your machine. Job text and CV excerpts go to Google Gemini for scoring; nothing else leaves
except scraping requests, optional ntfy pushes and tunnel traffic. Details: [PRIVACY.md](PRIVACY.md). Do not share your
`.env`, tunnel links, ntfy topic or LinkedIn cookie.
