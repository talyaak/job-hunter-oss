from app import notify


def test_skips_publish_when_topic_not_configured(monkeypatch):
    monkeypatch.setattr(notify.settings, "ntfy_topic", "")
    calls = []
    monkeypatch.setattr(notify.httpx, "post", lambda *a, **k: calls.append((a, k)))
    notify.notify_new_lead("Backend Developer", "Acme", 91, "https://jobs.example/1")
    assert calls == []


def test_publishes_json_with_topic_and_click_url(monkeypatch):
    monkeypatch.setattr(notify.settings, "ntfy_topic", "test-topic")
    monkeypatch.setattr(notify.settings, "ntfy_server", "https://ntfy.example/")
    calls = []

    class _Resp:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        calls.append((url, json))
        return _Resp()

    monkeypatch.setattr(notify.httpx, "post", fake_post)
    notify.notify_new_lead("Backend Developer", "Acme", 91, "https://jobs.example/1")

    url, body = calls[0]
    assert url == "https://ntfy.example"
    assert body["topic"] == "test-topic"
    assert body["title"] == "New lead 91: Acme"
    assert body["message"] == "Backend Developer"
    assert body["click"] == "https://jobs.example/1"


def test_publish_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(notify.settings, "ntfy_topic", "test-topic")

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(notify.httpx, "post", boom)
    assert notify.send_ntfy("title", "body") is False
