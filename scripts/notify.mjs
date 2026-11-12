// Send an ntfy push. Usage: node scripts/notify.mjs "<title>" "<message>" [clickUrl]
import { loadEnv } from "./lib/common.mjs";

export async function notify({ title, message, click, priority = "default", tags = "computer" }) {
  const env = loadEnv();
  const topic = (env.NTFY_TOPIC || "").trim();
  const server = (env.NTFY_SERVER || "https://ntfy.sh").replace(/\/$/, "");
  if (!topic) return { ok: false, reason: "NTFY_TOPIC is not set (run `npm run setup`)" };

  const headers = { Title: title, Priority: priority, Tags: tags };
  if (click) headers.Click = click;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(`${server}/${topic}`, {
        method: "POST",
        headers,
        body: message,
        signal: AbortSignal.timeout(10_000),
      });
      if (res.ok) return { ok: true };
      return { ok: false, reason: `ntfy responded ${res.status}` };
    } catch (err) {
      if (attempt === 3) return { ok: false, reason: `ntfy unreachable: ${err.cause?.code ?? err.message}` };
      await new Promise((r) => setTimeout(r, 1500 * attempt));
    }
  }
  return { ok: false, reason: "unknown" };
}

if (process.argv[1]?.endsWith("notify.mjs")) {
  const [, , title = "Job Hunter", message = "Test notification", click] = process.argv;
  const result = await notify({ title, message, click });
  console.log(result.ok ? "[notify] sent" : `[notify] failed: ${result.reason}`);
  process.exit(result.ok ? 0 : 1);
}
