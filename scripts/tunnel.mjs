// Start a private tunnel to the dev server and deliver the access link.
//
// Security model: the public URL alone gives nothing; the backend rejects every /api call without
// ACCESS_TOKEN. The link we print/push is  <tunnel>/?t=<token>  - the app exchanges it for an HttpOnly cookie
// and strips it from the address bar. Treat that link like a password.
//
// TUNNEL_NOTIFY_MODE (in .env):  link (default) = push the full link to your ntfy topic
//                                url            = push only the bare URL; you type the token yourself
//                                off            = print in this terminal only
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { TUNNEL_DIR, loadEnv, waitForHttp } from "./lib/common.mjs";
import { startQuickTunnel } from "./cloudflared.mjs";
import { notify } from "./notify.mjs";

const env = loadEnv();
const port = Number(process.argv[2] || env.FRONTEND_PORT || 5173);
const apiPort = Number(env.API_PORT || 8000);
const mode = (env.TUNNEL_NOTIFY_MODE || "link").toLowerCase();
const token = (env.ACCESS_TOKEN || "").trim();

if (!token) {
  console.error("[tunnel] ACCESS_TOKEN is empty - refusing to open a tunnel without one. Run `npm run setup` first.");
  process.exit(1);
}

console.log("[tunnel] waiting for the app to be ready...");
await waitForHttp(`http://127.0.0.1:${apiPort}/api/health/live`);
await waitForHttp(`http://127.0.0.1:${port}/`);

const { url, child } = await startQuickTunnel(port);
const link = `${url}/?t=${encodeURIComponent(token)}`;

mkdirSync(TUNNEL_DIR, { recursive: true });
writeFileSync(path.join(TUNNEL_DIR, "url"), url + "\n");

console.log("");
console.log("==============================================================");
console.log(`  Public URL : ${url}`);
console.log("  Private link (contains your access token; do not share):");
console.log(`  ${link}`);
console.log(`  Local      : http://localhost:${port}`);
console.log("==============================================================");
console.log("");

if (mode !== "off") {
  const result = await notify({
    title: "Job Hunter is online",
    message: mode === "url" ? `${url}\n(enter your access token when asked)` : "Tap to open your private Job Hunter link.",
    click: mode === "url" ? url : link,
    priority: "high",
  });
  console.log(result.ok ? `[tunnel] notification sent (mode: ${mode})` : `[tunnel] notification skipped: ${result.reason}`);
}

const stop = () => child.kill();
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
child.on("exit", (code) => process.exit(code ?? 0));
