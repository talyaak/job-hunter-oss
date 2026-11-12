# Third-party software

This project depends on, but does not bundle, the following (installed by `npm run setup`):

| Package | Use | License |
|---|---|---|
| [python-jobspy](https://github.com/speedyapply/JobSpy) | LinkedIn / Indeed scraping | MIT |
| FastAPI, Starlette, Uvicorn, SQLAlchemy, Alembic, pydantic, APScheduler, httpx, pypdf | backend | MIT / BSD |
| google-genai | Gemini API client | Apache-2.0 |
| Playwright (optional) | Google ATS search | Apache-2.0 |
| Vue, Vite, Tailwind CSS | frontend | MIT |
| cloudflared (external binary, optional) | quick tunnel | Apache-2.0 |
| ntfy (external service, optional) | push notifications | Apache-2.0 / GPLv2 |

Check each package's license before redistributing a bundled build.
