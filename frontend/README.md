# Frontend

Vue 3 + Vite 8 + Tailwind 4 dashboard. Run everything from the repo root (`npm run dev`); see the root README.

- `npm --prefix frontend run build` type-checks and builds.
- The dev server listens on 127.0.0.1 and proxies `/api` (including the sync WebSocket) to the backend.
- `VITE_USE_MOCK=true` serves synthetic data for demos and screenshots.
