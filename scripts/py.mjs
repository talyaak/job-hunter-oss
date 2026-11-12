// Run a backend Python module with the project's interpreter.
//   node scripts/py.mjs -m app.doctor_cli --probe
// `--tunnel` is expanded to `--tunnel-url <url written by the tunnel script>`.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { BACKEND, TUNNEL_DIR, findPython, runSync } from "./lib/common.mjs";

const args = process.argv.slice(2);
const i = args.indexOf("--tunnel");
if (i >= 0) {
  args.splice(i, 1);
  const file = path.join(TUNNEL_DIR, "url");
  if (existsSync(file)) args.push("--tunnel-url", readFileSync(file, "utf8").trim());
  else console.error("[doctor] no .tunnel/url found; start `npm run dev:tunnel` first");
}
process.exit(runSync(findPython(), args, { cwd: BACKEND }));
