# Windows guide

Job Hunter is built to run **natively on Windows**: every script is plain Node, no bash, no WSL required. This page
tells you what to install, and when WSL or Docker is actually worth it.

## What you need (native, the recommended path)

| Need | Why | Install (PowerShell) |
|---|---|---|
| **Node.js 18+** | runs the dev scripts (`npm run setup`, `dev`, `doctor`, tunnel) and the Vue frontend | `winget install OpenJS.NodeJS.LTS` |
| **Python 3.11+** | runs the backend (FastAPI), the job scraping and the Gemini calls | `winget install Python.Python.3.12` |
| **Git** | clone the repo | `winget install Git.Git` |
| **Gemini API key** | the AI scoring; free at https://aistudio.google.com/apikey | (browser) |
| *Optional:* **cloudflared** | the private tunnel to open the dashboard from your phone | `winget install Cloudflare.cloudflared` |
| *Optional:* **ntfy app** (phone) | push alerts for new leads and your private link | Play Store / App Store |

After installing, **open a new terminal** so PATH updates. Check with `node -v` and `python --version`.

```powershell
git clone <repo-url> job-hunter
cd job-hunter
npm run setup
npm run dev
```

You do **not** need to open any firewall ports: the API and dashboard listen on `127.0.0.1` only, and `cloudflared`
only makes outbound connections.

### Windows traps (and fixes)
- **`python` opens the Microsoft Store.** Turn off Settings > Apps > Advanced app settings > App execution aliases >
  `python.exe`/`python3.exe`, install Python with winget, and open a new terminal. `py -3` also works: setup tries it.
- **"DLL load failed ... Application Control policy".** A managed laptop's security policy blocks freshly installed
  compiled Python packages (numpy, pandas, SQLAlchemy). Ask IT to allow `backend\.venv`, or use WSL or Docker below,
  which sidestep the policy.
- **Tunnel link "site can't be reached" right after start.** Brand new `trycloudflare.com` names can take a minute;
  Windows may cache the failure. Wait, or run `ipconfig /flushdns`, or test on your phone using mobile data.
- **PowerShell script policy errors.** Not applicable: npm scripts call Node, not `.ps1` files.
- **Very long paths.** Clone to a short path such as `C:\dev\job-hunter` if `npm install` complains.
- **Antivirus slows the first install.** Normal: it scans thousands of small files in `node_modules` and `.venv`.

## Why WSL (optional)

**WSL2** is a real Linux running inside a lightweight virtual machine on Windows. You do not need it for Job Hunter, but
it helps when:

- you or your tools prefer Linux (bash, `apt`, Linux-only tooling), or want the same environment as the CI Linux runner;
- your Windows security policy blocks the Python packages (Linux binaries inside WSL are not subject to that policy);
- **Docker Desktop uses WSL2 under the hood** anyway, so if you install Docker you already have it.

If you use WSL:
1. `wsl --install -d Ubuntu`, restart if asked, create your Linux user.
2. Inside Ubuntu: install Node 18+ (nvm or NodeSource), `sudo apt install python3 python3-venv python3-pip git lsof`.
3. **Keep the repo in the Linux filesystem** (`~/job-hunter`), not under `/mnt/c/...`: it is much faster and file
   watching works.
4. Run the same commands (`npm run setup`, `npm run dev`). Open `http://localhost:5173` from your Windows browser;
   WSL forwards localhost automatically.
5. For the phone tunnel, install `cloudflared` inside Ubuntu (Cloudflare publishes a `.deb`), then `npm run dev:tunnel`.

## Why Docker (optional)

**Docker** packages the backend and frontend with all their dependencies, so you install neither Python nor Node and
nothing touches your system Python. Use it when:

- you want a reproducible, isolated install ("it works the same as on the maintainer's machine");
- native Python packages are blocked on your machine (see above);
- you want to throw the whole thing away cleanly (`docker compose down -v`).

Trade-offs: it needs **Docker Desktop with the WSL2 backend** (a large install; check its license terms for your use),
the dev loop is a bit slower, and **the access token is always required**, even on localhost, because requests inside
containers do not look local. Open `http://localhost:5173/?t=<ACCESS_TOKEN from .env>`.

```powershell
copy .env.example .env
docker compose up --build
docker compose run --rm api python -m app.onboard     # interactive setup inside the container
```
Your data lives in `backend\data` on the host. For the phone tunnel run `npm run tunnel` on the host (needs Node and
cloudflared there).

## Which should I choose?

| Your situation | Choose |
|---|---|
| Personal Windows PC, no restrictions | **Native** (simplest, fastest) |
| Managed/work laptop that blocks Python packages | **Docker** or **WSL** |
| You like Linux tooling or already use WSL | **WSL** |
| You want zero installs besides Docker Desktop | **Docker** |

## Quick Windows checklist
- [ ] `node -v` shows 18+, `python --version` shows 3.11+, `git --version` works
- [ ] `npm run setup` finishes and `npm run doctor` shows no FAIL (except a missing key/CV before you add them)
- [ ] `npm run dev` opens `http://localhost:5173`
- [ ] (optional) `cloudflared --version` works, then `npm run dev:tunnel`
- [ ] (optional) ntfy app installed and subscribed to the topic setup printed
