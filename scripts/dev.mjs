// One command to run everything.   node scripts/dev.mjs [--tunnel]
//   backend (uvicorn, bound to 127.0.0.1) + frontend (Vite) [+ private tunnel]
import path from "node:path";
import { BACKEND, FRONTEND, ROOT, findPython, loadEnv, prefixOutput, run, waitForHttp } from "./lib/common.mjs";
import { killPort } from "./kill-ports.mjs";

const withTunnel = process.argv.includes("--tunnel");
const env = loadEnv();
const apiPort = Number(env.API_PORT || 8000);
const apiHost = env.API_HOST || "127.0.0.1";
const fePort = Number(env.FRONTEND_PORT || 5173);

for (const p of [apiPort, fePort]) killPort(p);

const children = [];
let closing = false;

function shutdown(code = 0) {
  if (closing) return;
  closing = true;
  for (const c of children) {
    try {
      c.kill();
    } catch {
      /* ignore */
    }
  }
  setTimeout(() => process.exit(code), 500);
}

function start(label, color, cmd, args, opts = {}) {
  const child = run(cmd, args, { stdio: ["ignore", "pipe", "pipe"], ...opts });
  prefixOutput(child, label, color);
  child.on("exit", (code) => {
    console.log(`[${label}] exited (${code})`);
    shutdown(code ?? 0);
  });
  children.push(child);
  return child;
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

const python = findPython();
start("api", "\x1b[34m", python, ["-m", "uvicorn", "app.main:app", "--host", apiHost, "--port", String(apiPort)], {
  cwd: BACKEND,
});
start("web", "\x1b[32m", "npm", ["run", "dev"], {
  cwd: FRONTEND,
  env: { ...process.env, API_PROXY_TARGET: `http://127.0.0.1:${apiPort}` },
});

try {
  await waitForHttp(`http://127.0.0.1:${apiPort}/api/health/live`);
  await waitForHttp(`http://127.0.0.1:${fePort}/`);
  console.log(`\n  Local app: http://localhost:${fePort}\n  (first run? finish the setup wizard in the app, or run \`npm run setup\`)\n`);
} catch (err) {
  console.error(`[dev] ${err.message}`);
  shutdown(1);
}

if (withTunnel) {
  start("tunnel", "\x1b[35m", process.execPath, [path.join(ROOT, "scripts", "tunnel.mjs"), String(fePort)], { cwd: ROOT });
}
