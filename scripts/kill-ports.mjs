// Free dev ports before starting (cross-platform). Usage: node scripts/kill-ports.mjs 5173 8000
import { spawnSync } from "node:child_process";
import { isWindows } from "./lib/common.mjs";

export function pidsOnPort(port) {
  if (isWindows) {
    const r = spawnSync("netstat", ["-ano", "-p", "tcp"], { encoding: "utf8" });
    const pids = new Set();
    for (const line of (r.stdout || "").split(/\r?\n/)) {
      const parts = line.trim().split(/\s+/);
      if (parts.length >= 5 && parts[3] === "LISTENING" && parts[1].endsWith(`:${port}`)) pids.add(parts[4]);
    }
    return [...pids];
  }
  const r = spawnSync("lsof", ["-ti", `tcp:${port}`, "-sTCP:LISTEN"], { encoding: "utf8" });
  return (r.stdout || "").split(/\s+/).filter(Boolean);
}

export function killPort(port) {
  for (const pid of pidsOnPort(port)) {
    if (!pid || pid === "0") continue;
    if (isWindows) spawnSync("taskkill", ["/PID", pid, "/F", "/T"], { stdio: "ignore" });
    else spawnSync("kill", ["-9", pid], { stdio: "ignore" });
    console.log(`[ports] freed ${port} (pid ${pid})`);
  }
}

if (process.argv[1]?.endsWith("kill-ports.mjs")) {
  const ports = process.argv.slice(2).map(Number).filter(Boolean);
  for (const p of ports.length ? ports : [5173, 8000]) killPort(p);
}
