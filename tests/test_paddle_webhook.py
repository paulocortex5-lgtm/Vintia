"""Paddle webhook tests: signature verification + idempotent credit apply.

No network and no real keys: ``handle_webhook`` accepts an injected fake
client and the signature is computed locally with the same HMAC-SHA256
scheme Paddle documents (§G.3).
"""

import hashlib
import hmac
import json
import sys
import time
import types

import pytest

from engine.credits.paddle_webhook import handle_webhook, verify_signature
from engine.errors import PaddleError

SECRET = "pwl_test_destination_secret"
EVENT_ID = "evt_abc123"
USER_ID = "user_123"


class FakeSupabaseClient:
    """In-memory stand-in for engine.persistence.SupabaseClient."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def query(self, table, filters, select="*", *, service=False):
        column = next(iter(filters))
        value = filters[column].split("=", 1)[-1]
        return [row for row in self.rows if row.get(column) == value]

    def upsert(self, table, rows, *, service=False):
        self.rows.extend(rows)
        return True


def _event(event_id: str = EVENT_ID, event_type: str = "transaction.completed") -> bytes:
    return json.dumps(
        {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": "2026-10-04T00:00:00Z",
            "custom_data": {"user_id": USER_ID, "pack_id": "pack_10k", "credits": "10000"},
        }
    ).encode()


def _sign(body: bytes | None = None, secret: str = SECRET, *, offset_sec: float = 0.0) -> str:
    """Build a ``ts=..;h1=..`` header; ``body=None`` signs the sample event."""
    body = _event() if body is None else body
    ts = str(int(time.time() + offset_sec))
    signature = hmac.new(
        secret.encode(), f"{ts}:{body.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    return f"ts={ts};h1={signature}"


@pytest.fixture(autouse=True)
def _paddle_secret(monkeypatch):
    """handle_webhook() reads the destination secret from the environment."""
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", SECRET)
    return SECRET


# ── Signature verification (R49) ──────────────────────────────────────


def test_verify_signature_accepts_valid_header():
    body = _event()
    assert verify_signature(body, _sign(body), SECRET)


def test_verify_signature_rejects_wrong_secret():
    body = _event()
    assert not verify_signature(body, _sign(secret="wrong-secret"), SECRET)
    assert not verify_signature(body, _sign(body), "other-secret")


def test_verify_signature_rejects_stale_timestamp():
    body = _event()
    assert not verify_signature(body, _sign(offset_sec=-60.0), SECRET)


def test_verify_signature_rejects_missing_secret_or_header():
    body = _event()
    assert not verify_signature(body, _sign(body), secret="")
    assert not verify_signature(body, "", SECRET)
    assert not verify_signature(body, "ts=1;h1=deadbeef", SECRET)


# ── Idempotent processing (R50) ───────────────────────────────────────


def test_handle_webhook_records_event_and_is_idempotent():
    client = FakeSupabaseClient()
    body = _event()
    header = _sign(body)

    first = handle_webhook(body, header, supabase_client=client)
    assert first["status"] == "ledger_pending"
    assert first["event_id"] == EVENT_ID
    assert first["ledger"] == "unavailable"  # Phase 11 ledger not built yet

    row = client.rows[0]
    assert row["event_id"] == EVENT_ID
    assert row["credits"] == 10000
    assert row["user_id"] == USER_ID
    assert row["status"] == "ledger_pending"
    assert row["data"] == json.loads(body)
    assert row["processed_at"].endswith("Z")

    # Paddle retries on any non-200; a re-delivery must be a no-op.
    assert handle_webhook(body, header, supabase_client=client) == {
        "status": "already_processed",
        "event_id": EVENT_ID,
    }
    assert len(client.rows) == 1


def test_handle_webhook_ignores_non_completed_events():
    client = FakeSupabaseClient()
    body = _event(event_id="evt_failed", event_type="transaction.payment_failed")
    result = handle_webhook(body, _sign(body), supabase_client=client)
    assert result["status"] == "recorded"
    assert result["ledger"] == "not_required"
    assert client.rows[0]["credits"] == 10000  # stored, never applied


def test_handle_webhook_applies_credits_through_the_ledger(monkeypatch):
    calls: list[tuple] = []

    class LedgerModule(types.ModuleType):
        def topup_from_paddle(self, user_id, credits, event_id):
            calls.append((user_id, credits, event_id))

    monkeypatch.setitem(sys.modules, "engine.credits.ledger", LedgerModule("engine.credits.ledger"))

    client = FakeSupabaseClient()
    body = _event()
    result = handle_webhook(body, _sign(body), supabase_client=client)
    assert result == {"status": "credited", "event_id": EVENT_ID, "ledger": "ok"}
    assert calls == [(USER_ID, 10000, EVENT_ID)]


def test_handle_webhook_invalid_signature_raises():
    with pytest.raises(PaddleError, match="Paddle-Signature"):
        handle_webhook(_event(), "ts=1;h1=deadbeef", supabase_client=FakeSupabaseClient())
