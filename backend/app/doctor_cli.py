"""``python -m app.doctor_cli`` : health check of the configuration and (optionally) a running server.

Examples
  python -m app.doctor_cli                      # config + dependency checks (no network)
  python -m app.doctor_cli --probe              # also call Gemini / LinkedIn / ntfy
  python -m app.doctor_cli --sweep              # also hit every API route on the running backend
  python -m app.doctor_cli --sweep --tunnel-url https://x.trycloudflare.com   # verify the gate
  python -m app.doctor_cli --models             # list Gemini models your key can call
  python -m app.doctor_cli --json               # machine-readable (CI)
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from app.config import REPO_ROOT, settings
from app.db.session import Base, SessionLocal, engine
from app.doctor import Check, run_checks, summarize

# (method, path, acceptable status codes). Live-scraping endpoints are deliberately not called.
ROUTE_SWEEP: list[tuple[str, str, tuple[int, ...]]] = [
    ("GET", "/api/health/live", (200,)),
    ("GET", "/api/health", (200,)),
    ("GET", "/api/health/deep", (200,)),
    ("GET", "/api/auth/status", (200,)),
    ("GET", "/api/leads", (200,)),
    ("GET", "/api/rejects", (200,)),
    ("GET", "/api/rejects/unscored/count", (200,)),
    ("GET", "/api/profile", (200,)),
    ("GET", "/api/profile/apply", (200,)),
    ("GET", "/api/sync/status", (200,)),
    ("GET", "/api/sync/latest", (200,)),
    ("GET", "/api/preferences", (200,)),
    ("GET", "/api/onboarding/status", (200,)),
    ("GET", "/api/insights/summary", (200,)),
    ("GET", "/api/search/linkedin/history", (200,)),
    ("GET", "/api/search/linkedin/filters", (200,)),
]
SYMBOL = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "skip": "SKIP"}


def sweep_routes(base_url: str, token: str) -> list[Check]:
    out: list[Check] = []
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=15, headers=headers) as client:
        for method, path, ok in ROUTE_SWEEP:
            try:
                r = client.request(method, path)
            except Exception as exc:  # noqa: BLE001
                out.append(Check(f"route {method} {path}", "fail", f"unreachable: {exc}", "Is the backend running? `npm run dev`"))
                break
            status = "pass" if r.status_code in ok else "fail"
            fix = ""
            if status == "fail":
                fix = "401 means the access token is wrong or missing" if r.status_code == 401 else "See backend logs"
            out.append(Check(f"route {method} {path}", status, f"HTTP {r.status_code}", fix))
    return out


def check_gate(tunnel_url: str, token: str) -> list[Check]:
    """Through the public URL: no token must be rejected, the token must work."""
    out: list[Check] = []
    base = tunnel_url.rstrip("/")
    try:
        anon = httpx.get(f"{base}/api/leads", timeout=20)
        out.append(
            Check("tunnel gate (no token)", "pass" if anon.status_code == 401 else "fail", f"HTTP {anon.status_code}",
                  "" if anon.status_code == 401 else "The tunnel exposes data without a token! Stop it and check ACCESS_TOKEN")
        )
        authed = httpx.get(f"{base}/api/leads", headers={"Authorization": f"Bearer {token}"}, timeout=20)
        out.append(Check("tunnel gate (with token)", "pass" if authed.status_code == 200 else "fail", f"HTTP {authed.status_code}"))
        live = httpx.get(f"{base}/api/health/live", timeout=20)
        out.append(Check("tunnel liveness", "pass" if live.status_code == 200 else "fail", f"HTTP {live.status_code}"))
    except Exception as exc:  # noqa: BLE001
        out.append(Check("tunnel reachable", "fail", str(exc)[:200], "Is `npm run dev:tunnel` running? DNS can lag for a minute"))
    return out


def check_websocket(base_url: str, token: str) -> Check:
    try:
        import websockets.sync.client as ws_client
    except Exception:  # noqa: BLE001
        return Check("websocket", "skip", "websockets package not installed")
    url = base_url.replace("http", "ws", 1).rstrip("/") + "/api/sync/ws"
    try:
        with ws_client.connect(url, additional_headers={"Authorization": f"Bearer {token}"} if token else {}, open_timeout=8):
            return Check("websocket /api/sync/ws", "pass", "handshake ok")
    except Exception as exc:  # noqa: BLE001
        return Check("websocket /api/sync/ws", "fail", str(exc)[:200], "Backend not running or token rejected")


def print_table(checks: list[Check]) -> None:
    width = max(len(c.name) for c in checks)
    for c in checks:
        print(f"[{SYMBOL[c.status]}] {c.name.ljust(width)}  {c.detail}")
        if c.fix and c.status in ("warn", "fail"):
            print(f"       -> {c.fix}")
    print(f"\nOverall: {SYMBOL[summarize(checks)]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="doctor")
    ap.add_argument("--probe", action="store_true", help="call Gemini/LinkedIn/ntfy for real")
    ap.add_argument("--sweep", action="store_true", help="hit all API routes on --base-url")
    ap.add_argument("--base-url", default=f"http://127.0.0.1:{settings.api_port}")
    ap.add_argument("--tunnel-url", default="", help="public URL to verify the access gate")
    ap.add_argument("--models", action="store_true", help="list Gemini models your key can use and exit")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.models:
        from app.llm.client import list_models

        try:
            found = list_models()
        except Exception as exc:  # noqa: BLE001
            print(f"Could not list models: {exc}")
            return 1
        if args.json:
            print(json.dumps(found, indent=2))
        else:
            print("Generation: " + ", ".join(found["generate"]))
            print()
            print("Embedding: " + ", ".join(found["embed"]))
        print()
        print(
            f"Current: GEMINI_MODEL={settings.gemini_model}, "
            f"EMBEDDING_MODEL={settings.embedding_model}, GEMMA_MODEL={settings.gemma_model}"
        )
        return 0

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        checks = run_checks(db, probe=args.probe)

    if args.sweep:
        checks += sweep_routes(args.base_url, settings.access_token)
        checks.append(check_websocket(args.base_url, settings.access_token))
    if args.tunnel_url:
        checks += check_gate(args.tunnel_url, settings.access_token)

    if args.json:
        print(json.dumps({"status": summarize(checks), "checks": [c.as_dict() for c in checks]}, indent=2))
    else:
        print(f"Repo: {REPO_ROOT}\n")
        print_table(checks)
    return 1 if summarize(checks) == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
