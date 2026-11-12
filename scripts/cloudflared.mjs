// Cloudflare quick tunnel launcher (trycloudflare.com). No account needed.
import { closeSync, existsSync, mkdirSync, openSync, unlinkSync } from "node:fs";
import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import { TUNNEL_DIR, isWindows, sleep } from "./lib/common.mjs";

const lockFile = path.join(TUNNEL_DIR, "register.lock");

export function resolveCloudflared() {
  const candidates = isWindows
    ? ["cloudflared", "C:\\Program Files (x86)\\cloudflared\\cloudflared.exe", "C:\\Program Files\\cloudflared\\cloudflared.exe"]
    : ["cloudflared", "/usr/local/bin/cloudflared", "/opt/homebrew/bin/cloudflared"];
  for (const c of candidates) {
    if (c === "cloudflared") {
      if (spawnSync(c, ["--version"], { stdio: "ignore" }).status === 0) return c;
    } else if (existsSync(c)) return c;
  }
  throw new Error(
    "cloudflared not found. Install it (Windows: winget install Cloudflare.cloudflared, macOS: brew install cloudflared, " +
      "Linux: see docs/TUNNEL.md) and re-run."
  );
}

async function acquireLock(timeoutMs = 120_000) {
  mkdirSync(TUNNEL_DIR, { recursive: true });
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      closeSync(openSync(lockFile, "wx"));
      return () => {
        try {
          unlinkSync(lockFile);
        } catch {
          /* ignore */
        }
      };
    } catch {
      await sleep(1000);
    }
  }
  throw new Error("tunnel registration lock timeout (delete .tunnel/register.lock if no tunnel is starting)");
}

function startOnce(binary, target) {
  return new Promise((resolve, reject) => {
    // Always target the Vite dev server; it proxies /api to the loopback-bound backend.
    const child = spawn(binary, ["tunnel", "--no-autoupdate", "--url", target], { stdio: ["ignore", "pipe", "pipe"] });
    let buffer = "";
    let found = false;
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("cloudflared did not print a tunnel URL within 60s"));
    }, 60_000);
    const onData = (chunk) => {
      buffer += chunk.toString();
      const m = buffer.match(/https:\/\/[a-z0-9-]+\.trycloudflare\.com/i);
      if (m && !found) {
        found = true;
        clearTimeout(timer);
        resolve({ url: m[0], child });
      }
      if (/failed to parse quick Tunnel ID|failed to unmarshal quick Tunnel/i.test(buffer)) {
        clearTimeout(timer);
        child.kill();
        reject(new Error("cloudflared quick tunnel registration failed"));
      }
    };
    child.stdout.on("data", onData);
    child.stderr.on("data", onData);
    child.on("exit", (code) => {
      if (!found) {
        clearTimeout(timer);
        reject(new Error(`cloudflared exited with ${code}`));
      }
    });
  });
}

export async function startQuickTunnel(port, { retries = 5 } = {}) {
  const binary = resolveCloudflared();
  let lastError;
  for (let attempt = 1; attempt <= retries; attempt++) {
    const release = await acquireLock();
    try {
      const result = await startOnce(binary, `http://127.0.0.1:${port}`);
      release();
      return result;
    } catch (err) {
      release();
      lastError = err;
      if (attempt < retries) {
        console.error(`[tunnel] attempt ${attempt} failed: ${err.message}, retrying...`);
        await sleep(2000 * attempt);
      }
    }
  }
  throw lastError;
}
