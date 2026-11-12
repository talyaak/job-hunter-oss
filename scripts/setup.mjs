// First-run setup: virtualenv + dependencies + migrations + interactive onboarding.
//   npm run setup [-- --yes --gemini-key ... --cv path.pdf --titles "A, B" --location "City"]
//   npm run setup -- --skip-install     (re-run onboarding only)
import { existsSync } from "node:fs";
import path from "node:path";
import { BACKEND, FRONTEND, findPython, isWindows, runSync } from "./lib/common.mjs";

function step(msg) {
  console.log(`\n\x1b[1m> ${msg}\x1b[0m`);
}

function must(code, what) {
  if (code !== 0) {
    console.error(`\nSetup failed during: ${what}`);
    process.exit(code);
  }
}

const args = process.argv.slice(2);
const skipInstall = args.includes("--skip-install");
const passthrough = args.filter((a) => a !== "--skip-install");

if (!skipInstall) {
  const venv = path.join(BACKEND, ".venv");
  if (!existsSync(venv)) {
    step("Creating Python virtualenv (backend/.venv)");
    must(runSync(isWindows ? "python" : "python3", ["-m", "venv", venv]), "python -m venv");
  }
  const py = findPython();
  step("Installing backend dependencies");
  must(runSync(py, ["-m", "pip", "install", "--upgrade", "pip"], { cwd: BACKEND }), "pip upgrade");
  must(runSync(py, ["-m", "pip", "install", "-e", ".[dev]"], { cwd: BACKEND }), "pip install");

  step("Installing frontend dependencies");
  must(runSync("npm", ["install"], { cwd: FRONTEND }), "npm install (frontend)");
}

step("Applying database migrations");
const py = findPython();
must(runSync(py, ["-m", "alembic", "upgrade", "head"], { cwd: BACKEND }), "alembic upgrade head");

step("Onboarding");
process.exit(runSync(py, ["-m", "app.onboard", ...passthrough], { cwd: BACKEND }));
