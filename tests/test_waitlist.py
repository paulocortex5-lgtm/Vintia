"""Waitlist double opt-in tests (task 5.6) — no network, no faked sends."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from engine.errors import VantiaError
from engine.waitlist import OutboxSender, WaitlistService, normalize_email


class FakeSupabase:
    """In-memory waitlist table honoring the eq.-filter convention."""

    configured = True

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def query(self, table, filters, select="*", *, service=False):
        column, raw_filter = next(iter(filters.items()))
        raw = raw_filter.partition("eq.")[2]
        return [dict(r) for r in self.rows if str(r.get(column)) == raw]

    def upsert(self, table, rows, *, service=False):
        for row in rows:
            self.rows = [r for r in self.rows if r["email"] != row["email"]]
            self.rows.append(dict(row))
        return True


class RecordingSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_confirmation(self, email, token):
        self.sent.append((email, token))
        return "recording://sent"


@pytest.fixture()
def service():
    return WaitlistService(supabase_client=FakeSupabase(), sender=RecordingSender())


# ── Email + service ────────────────────────────────────────────────────


def test_normalize_email_lowercases_and_refuses_junk():
    assert normalize_email("  Ada@Example.COM ") == "ada@example.com"
    for bad in ("", "no-at-sign", "a@b", "a b@c.com", "a@b.c" + "x" * 300):
        with pytest.raises(VantiaError) as excinfo:
            normalize_email(bad)
        assert excinfo.value.code == "invalid_email"


def test_subscribe_is_pending_not_confirmed(service):
    result = service.subscribe("Ada@Example.com")
    assert result == {"email": "ada@example.com", "status": "pending", "confirmation_sent": True}
    # stored row never contains the raw token — only its sha256
    row = service.client.rows[0]
    token = service.sender.sent[0][1]
    assert row["status"] == "pending"
    assert row["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in json.dumps(row)


def test_double_opt_in_flow_confirms_exactly_once(service):
    service.subscribe("ada@example.com")
    token = service.sender.sent[0][1]

    first = service.confirm(token)
    assert first["status"] == "confirmed" and first["already"] is False
    replay = service.confirm(token)
    assert replay["status"] == "confirmed" and replay["already"] is True
    assert service.stats() == {"confirmed_count": 1, "pending_count": 0}


def test_resubscribing_rotates_the_token(service):
    service.subscribe("ada@example.com")
    old_token = service.sender.sent[0][1]
    service.subscribe("ada@example.com")
    new_token = service.sender.sent[1][1]
    assert old_token != new_token
    with pytest.raises(VantiaError) as excinfo:
        service.confirm(old_token)
    assert excinfo.value.code == "waitlist_token_invalid"
    assert service.confirm(new_token)["status"] == "confirmed"


def test_confirmed_addresses_are_not_reinvited(service):
    service.subscribe("ada@example.com")
    service.confirm(service.sender.sent[0][1])
    result = service.subscribe("ada@example.com")
    assert result["confirmation_sent"] is False
    assert result["status"] == "confirmed"
    assert len(service.sender.sent) == 1  # no new email


def test_bad_tokens_refuse_with_stable_codes(service):
    with pytest.raises(VantiaError) as e1:
        service.confirm("")
    assert e1.value.code == "waitlist_token_required"
    with pytest.raises(VantiaError) as e2:
        service.confirm("not-a-real-token")
    assert e2.value.code == "waitlist_token_invalid"


def test_unconfigured_backend_refuses_loudly():
    class Unconfigured:
        configured = False

    service = WaitlistService(supabase_client=Unconfigured(), sender=RecordingSender())
    for call in (
        lambda: service.subscribe("a@b.co"),
        lambda: service.confirm("t"),
        lambda: service.stats(),
    ):
        with pytest.raises(VantiaError) as excinfo:
            call()
        assert excinfo.value.code == "waitlist_backend_unconfigured"


# ── Outbox sender (no provider configured yet) ─────────────────────────


def test_outbox_sender_writes_a_reviewable_message(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_OUTBOX_DIR", str(tmp_path))
    sender = OutboxSender()
    path = sender.send_confirmation("ada@example.com", "tok123")
    import json

    with open(path, encoding="utf-8") as fh:
        message = json.load(fh)
    assert message["to"] == "ada@example.com"
    assert message["token"] == "tok123"
    assert "not on the list" in message["body"]
    assert message["delivery"].startswith("outbox")


# ── API routes (task 5.6) ──────────────────────────────────────────────


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    fake = WaitlistService(supabase_client=FakeSupabase(), sender=RecordingSender())
    monkeypatch.setattr("engine.api._waitlist_service", lambda: fake)
    from engine.api import app

    with TestClient(app) as test_client:
        test_client.waitlist_service = fake  # type: ignore[attr-defined]
        yield test_client


def test_subscribe_route_never_leaks_the_token(client):
    response = client.post("/waitlist/subscribe", json={"email": "Ada@Example.com"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pending" and body["confirmation_sent"] is True
    assert "token" not in json.dumps(body)  # the token only ever reaches the email


def test_subscribe_validation_uses_stable_codes(client):
    response = client.post("/waitlist/subscribe", json={"email": "not-an-email"})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "invalid_email"


def test_confirm_route_full_flow(client):
    client.post("/waitlist/subscribe", json={"email": "ada@example.com"})
    token = client.waitlist_service.sender.sent[0][1]
    response = client.post("/waitlist/confirm", json={"token": token})
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    bad = client.post("/waitlist/confirm", json={"token": "wrong"})
    assert bad.status_code == 422
    assert bad.json()["detail"]["error"] == "waitlist_token_invalid"


def test_stats_route_counts_both_states(client):
    client.post("/waitlist/subscribe", json={"email": "ada@example.com"})
    stats = client.get("/waitlist/stats").json()
    assert stats == {
        "confirmed_count": 0,
        "pending_count": 1,
        "ts": stats["ts"],
    }


def test_unconfigured_backend_is_503_not_200(monkeypatch):
    monkeypatch.setenv("VANTIA_SELF_PING", "0")

    class Unconfigured:
        configured = False

    monkeypatch.setattr(
        "engine.api._waitlist_service",
        lambda: WaitlistService(supabase_client=Unconfigured(), sender=RecordingSender()),
    )
    from engine.api import app

    with TestClient(app) as client:
        response = client.post("/waitlist/subscribe", json={"email": "a@b.co"})
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "waitlist_backend_unconfigured"
