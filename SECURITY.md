# Security policy

## Threat model

Job Hunter is single-user and local-first. It holds your CV, API keys and (optionally) a LinkedIn session cookie, so
the main risks are **accidental exposure** and **leaking secrets**.

| Asset | Protection |
|---|---|
| API and sync WebSocket | Access gate: every `/api` request needs `ACCESS_TOKEN` (Bearer header, `X-Access-Token`, or the HttpOnly session cookie; WebSocket also `?t=`). Only `GET /api/health/live` and `/api/auth/*` are public. Requests that provably come from this machine (loopback peer, no tunnel headers, local original host) skip the token while `LOCAL_TRUST=true`. Failed attempts are rate limited. |
| Network surface | Backend and Vite bind to `127.0.0.1`. The tunnel only points at the Vite port, which proxies `/api`. |
| Secrets | In `.env` (gitignored). Never returned by the API (masked). Not logged. |
| Tunnel link | Contains the token; ntfy delivers it, so keep `NTFY_TOPIC` long and private, or use `TUNNEL_NOTIFY_MODE=url` / `off`. |
| Extension | Token stored in `chrome.storage.local` (not synced); narrow content-script matches. |

Not protected: someone with local access to your machine; anyone you give the private link or token to; the
Gemini/LinkedIn/ntfy services themselves. Rotate by deleting `ACCESS_TOKEN` from `.env`, restarting, and re-running
`npm run setup -- --skip-install`.

## Reporting a vulnerability

Please open a private security advisory on the repository (or email the maintainers listed there) with steps to
reproduce. Do not post exploits, tokens or personal data in public issues. We aim to acknowledge within a week.

## Hygiene for contributors

- Run `npm run doctor` and the secret scan (`gitleaks detect`) before pushing; CI does both.
- Never commit `.env`, databases, CVs, logs or tunnel URLs.
- Use synthetic personas in tests and fixtures.
