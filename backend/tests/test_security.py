import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import security
from app.config import settings
from app.main import app
from tests.conftest import TEST_TOKEN


@pytest.fixture(autouse=True)
def _reset_failures():
    security._FAILS.clear()


def anon() -> TestClient:
    return TestClient(app, headers={})  # not loopback ("testclient" peer) and no token


def test_api_requires_token():
    r = anon().get("/api/leads")
    assert r.status_code == 401


def test_liveness_and_auth_status_are_public():
    c = anon()
    assert c.get("/api/health/live").status_code == 200
    assert c.get("/api/auth/status").json()["authenticated"] is False


def test_bearer_token_and_header_token_work():
    assert anon().get("/api/preferences", headers={"Authorization": f"Bearer {TEST_TOKEN}"}).status_code == 200
    assert anon().get("/api/preferences", headers={"X-Access-Token": TEST_TOKEN}).status_code == 200


def test_wrong_token_rejected():
    assert anon().get("/api/preferences", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_session_exchange_sets_httponly_cookie_and_cookie_authenticates():
    c = anon()
    r = c.post("/api/auth/session", json={"token": TEST_TOKEN})
    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie
    assert c.get("/api/preferences").status_code == 200  # cookie jar carries it


def test_bad_session_token_rejected():
    assert anon().post("/api/auth/session", json={"token": "bad"}).status_code == 401


def test_rate_limit_after_repeated_failures():
    c = anon()
    for _ in range(security.FAIL_LIMIT + 1):
        c.get("/api/leads", headers={"Authorization": "Bearer wrong"})
    r = c.get("/api/leads", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert r.status_code == 429


def test_empty_server_token_never_authorizes(monkeypatch):
    monkeypatch.setattr(settings, "access_token", "")
    assert anon().get("/api/leads", headers={"Authorization": "Bearer "}).status_code == 401


def test_websocket_requires_token():
    with pytest.raises(WebSocketDisconnect):
        with anon().websocket_connect("/api/sync/ws"):
            pass


def test_websocket_with_token_connects():
    with anon().websocket_connect(f"/api/sync/ws?t={TEST_TOKEN}") as ws:
        assert ws is not None


def _scope(host=b"localhost:5173", peer=("127.0.0.1", 5000), extra=()):
    return {"type": "http", "headers": [(b"host", host), *extra], "client": peer}


def test_local_trust_only_for_untunnelled_loopback():
    assert security.is_local_request(_scope())
    assert not security.is_local_request(_scope(peer=("203.0.113.9", 1)))
    assert not security.is_local_request(_scope(extra=[(b"cf-connecting-ip", b"198.51.100.1")]))
    assert not security.is_local_request(_scope(host=b"abc.trycloudflare.com"))
    # Vite proxy stamps the original host; a tunnel request must not look local
    assert not security.is_local_request(_scope(extra=[(b"x-forwarded-host", b"abc.trycloudflare.com")]))
    assert security.is_local_request(_scope(extra=[(b"x-forwarded-host", b"localhost:5173")]))


def test_local_trust_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "local_trust", False)
    assert not security.is_authorized(_scope())
