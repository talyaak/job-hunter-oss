// Shared helpers for the dev scripts. Plain Node (>=18), no dependencies, works on Windows/macOS/Linux.
import { existsSync, readFileSync } from "node:fs";
import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const BACKEND = path.join(ROOT, "backend");
export const FRONTEND = path.join(ROOT, "frontend");
export const TUNNEL_DIR = path.join(ROOT, ".tunnel");
export const isWindows = process.platform === "win32";

export function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/** Parse the repo-root .env (KEY=VALUE, optional quotes). Real environment variables win. */
export function loadEnv() {
  const file = path.join(ROOT, ".env");
  const out = {};
  if (existsSync(file)) {
    for (const raw of readFileSync(file, "utf8").split(/\r?\n/)) {
      const line = raw.trim();
      if (!line || line.startsWith("#")) continue;
      const i = line.indexOf("=");
      if (i < 0) continue;
      const key = line.slice(0, i).trim();
      let value = line.slice(i + 1).trim();
      if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
        value = value.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, "\\");
      }
      out[key] = value;
    }
  }
  return { ...out, ...process.env };
}

/** Locate the project virtualenv's python, falling back to python3/python on PATH. */
export function findPython() {
  const venvCandidates = isWindows
    ? [path.join(BACKEND, ".venv", "Scripts", "python.exe")]
    : [path.join(BACKEND, ".venv", "bin", "python"), path.join(BACKEND, ".venv", "bin", "python3")];
  for (const c of venvCandidates) if (existsSync(c)) return c;
  for (const name of isWindows ? ["python", "py"] : ["python3", "python"]) {
    const r = spawnSync(name, ["--version"], { stdio: "ignore" });
    if (r.status === 0) return name;
  }
  throw new Error("Python 3.11+ not found. Install it, then run `npm run setup`.");
}

export function run(cmd, args, opts = {}) {
  return spawn(cmd, args, { stdio: "inherit", shell: isWindows && !path.isAbsolute(cmd), ...opts });
}

export function runSync(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: isWindows && !path.isAbsolute(cmd), ...opts });
  return r.status ?? 1;
}

export async function waitForHttp(url, { timeoutMs = 90_000, intervalMs = 700 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let lastErr;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
      if (res.ok) return true;
      lastErr = new Error(`HTTP ${res.status}`);
    } catch (err) {
      lastErr = err;
    }
    await sleep(intervalMs);
  }
  throw new Error(`Timed out waiting for ${url}: ${lastErr?.message ?? "unknown error"}`);
}

export function prefixOutput(child, label, color = "") {
  const reset = color ? "\x1b[0m" : "";
  const tag = `${color}[${label}]${reset} `;
  for (const stream of [child.stdout, child.stderr]) {
    if (!stream) continue;
    let buffer = "";
    stream.on("data", (chunk) => {
      buffer += chunk.toString();
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";
      for (const line of lines) if (line) console.log(tag + line);
    });
  }
}
