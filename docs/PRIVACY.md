# Privacy

Everything runs on your machine. This is what is stored and what leaves it.

## Stored locally

- `backend/data/job_hunter.db`: leads, rejects, run history, embeddings, your CV text, your preferences.
- `backend/data/resume.pdf`: your uploaded CV (used by the extension for autofill).
- `.env`: API keys, optional LinkedIn cookie, ntfy topic, access token.
All of these paths are gitignored. Delete `backend/data` to wipe the app's data.

## Sent to third parties

| Service | What is sent | When |
|---|---|---|
| Google Gemini | job title/company/description and your CV/profile text (truncated), similar past jobs | scoring, pre-filters, embeddings, cover letters |
| LinkedIn / Indeed / Google | search queries (your titles and location), job page requests, your `li_at` cookie to LinkedIn only if configured | each sweep |
| ntfy server | notification title/message (company, role, and the tunnel link if `TUNNEL_NOTIFY_MODE=link`) | new leads, tunnel start |
| Cloudflare | all tunnel traffic (it can see it, as with any reverse proxy) | only while the tunnel runs |
| SerpAPI (optional) | search queries | if `SERP_API_KEY` is set |

Review Google's terms for your Gemini tier (free-tier prompts may be used to improve products). If that is a concern,
use a paid/enterprise key or do not upload sensitive CV details.

## Agent skills

The skills read your data through the local API. They are instructed not to print secrets and not to paste your CV
into third-party tools. Generated CVs go to `cv_optimizer/output/` (gitignored).
