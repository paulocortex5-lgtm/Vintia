"""Tests for ``engine/api.py`` and ``engine/keep_alive.py`` (task 0.8).

``VANTIA_SELF_PING=0`` suppresses the daemon thread so the suite leaves no
background work behind.
"""

from engine import keep_alive
from engine.api import app, health


def test_health_payload_shape():
    body = health()
    assert body["status"] == "ok"
    assert body["service"] == "vantia-engine"
    assert body["version"] == "0.4.0"
    assert body["uptime_sec"] >= 0
    assert "ts" in body


def test_health_endpoint_via_testclient(monkeypatch):
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_startup_hook_respects_self_ping_switch(monkeypatch):
    """``VANTIA_SELF_PING=0`` must not spawn the daemon thread on startup."""
    import engine.api as api_module

    calls: list[str] = []
    monkeypatch.setattr(api_module, "start_self_ping", lambda: calls.append("ping"))
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    api_module._startup()
    assert calls == []

    monkeypatch.setenv("VANTIA_SELF_PING", "1")
    api_module._startup()
    assert calls == ["ping"]


def test_self_ping_interval_guard(monkeypatch):
    monkeypatch.setattr(keep_alive, "_thread", None)
    monkeypatch.setenv("VANTIA_SELF_PING_INTERVAL_SEC", "0")
    assert keep_alive.start_self_ping() is None
    monkeypatch.setattr(keep_alive, "_thread", None)


def test_self_ping_starts_a_daemon_and_is_idempotent(monkeypatch):
    monkeypatch.setattr(keep_alive, "_thread", None)
    monkeypatch.setenv("VANTIA_SELF_PING_INTERVAL_SEC", "600")
    thread = keep_alive.start_self_ping()
    assert thread is not None
    assert thread.daemon is True
    assert thread.name == "vantia-self-ping"
    assert keep_alive.start_self_ping() is thread
    monkeypatch.setattr(keep_alive, "_thread", None)

