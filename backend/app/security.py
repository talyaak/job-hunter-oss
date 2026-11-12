"""Access gate for the API and the sync WebSocket.

Threat model: the Cloudflare quick tunnel publishes the dev server at a public URL. Anyone who learns the
hostname must NOT be able to read leads, your CV or trigger syncs. So every ``/api`` request needs the
access token, except:

* ``/api/health/live`` and ``/api/auth/*`` (needed to sign in), and
* requests that provably come from this machine (no tunnel headers, loopback peer, local original host)
  while ``LOCAL_TRUST`` is on, so ``localhost:5173`` just works.

The gate is a pure ASGI middleware so it covers WebSockets too.
"""

from __future__ import annotations

import json
import secrets
import time
from collections import defaultdict, deque
from http.cookies import SimpleCookie

from app.config import settings

COOKIE_NAME = "jh_access"
EXEMPT_EXACT = {"/api/health/live"}
EXEMPT_PREFIX = ("/api/auth/",)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
LOOPBACK_PEERS = {"127.0.0.1", "::1", "localhost"}
# Headers a Cloudflare tunnel (or any reverse proxy) adds; their presence means "not a local request".
PROXY_HEADERS = (b"cf-connecting-ip", b"cf-ray", b"cf-visitor", b"cf-ipcountry", b"x-forwarded-for", b"forwarded")

_FAILS: dict[str, deque[float]] = defaultdict(deque)
FAIL_WINDOW_SECONDS = 300
FAIL_LIMIT = 10


def token_matches(candidate: str | None) -> bool:
    expected = settings.access_token
    if not expected or not candidate:
        return False
    return secrets.compare_digest(candidate.encode(), expected.encode())


def _headers(scope) -> dict[bytes, bytes]:
    return {k.lower(): v for k, v in scope.get("headers", [])}


def _host_name(value: str) -> str:
    value = value.strip().lower()
    if value.startswith("["):
        return value.split("]")[0] + "]"
    return value.split(":")[0]


def is_local_request(scope) -> bool:
    """True only for requests that did not arrive through a proxy/tunnel."""
    headers = _headers(scope)
    if any(h in headers for h in PROXY_HEADERS):
        return False
    client = scope.get("client")
    if not client or client[0] not in LOOPBACK_PEERS:
        return False
    # The Vite proxy rewrites Host (changeOrigin) but stamps the original host here.
    original = headers.get(b"x-forwarded-host") or headers.get(b"host")
    if original and _host_name(original.decode("latin-1")) not in LOCAL_HOSTS:
        return False
    return True


def extract_token(scope) -> str | None:
    headers = _headers(scope)
    auth = headers.get(b"authorization", b"").decode("latin-1")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    direct = headers.get(b"x-access-token")
    if direct:
        return direct.decode("latin-1").strip()
    cookie_header = headers.get(b"cookie")
    if cookie_header:
        jar: SimpleCookie = SimpleCookie()
        try:
            jar.load(cookie_header.decode("latin-1"))
        except Exception:  # noqa: BLE001
            jar = SimpleCookie()
        if COOKIE_NAME in jar:
            return jar[COOKIE_NAME].value
    if scope["type"] == "websocket":
        from urllib.parse import parse_qs

        qs = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        if qs.get("t"):
            return qs["t"][0]
    return None


def client_key(scope) -> str:
    headers = _headers(scope)
    forwarded = headers.get(b"cf-connecting-ip") or headers.get(b"x-forwarded-for")
    if forwarded:
        return forwarded.decode("latin-1").split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


def record_failure(key: str) -> bool:
    """Record a failed attempt; returns True when the client is now rate limited."""
    now = time.monotonic()
    bucket = _FAILS[key]
    while bucket and now - bucket[0] > FAIL_WINDOW_SECONDS:
        bucket.popleft()
    bucket.append(now)
    return len(bucket) > FAIL_LIMIT


def is_rate_limited(key: str) -> bool:
    now = time.monotonic()
    bucket = _FAILS[key]
    while bucket and now - bucket[0] > FAIL_WINDOW_SECONDS:
        bucket.popleft()
    return len(bucket) > FAIL_LIMIT


def is_authorized(scope) -> bool:
    if settings.local_trust and is_local_request(scope):
        return True
    return token_matches(extract_token(scope))


class AccessGateMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if (
            not path.startswith("/api")
            or path in EXEMPT_EXACT
            or path.startswith(EXEMPT_PREFIX)
            or (scope["type"] == "http" and scope.get("method") == "OPTIONS")
        ):
            await self.app(scope, receive, send)
            return

        key = client_key(scope)
        if is_rate_limited(key):
            await self._deny(scope, receive, send, 429, "Too many failed attempts")
            return

        if is_authorized(scope):
            await self.app(scope, receive, send)
            return

        # Only count attempts that actually presented a (wrong) token toward the limit.
        if extract_token(scope):
            record_failure(key)
        await self._deny(scope, receive, send, 401, "Access token required")

    @staticmethod
    async def _deny(scope, receive, send, status: int, detail: str):
        if scope["type"] == "websocket":
            await receive()  # consume websocket.connect
            await send({"type": "websocket.close", "code": 1008})
            return
        body = json.dumps({"detail": detail}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})
