"""Paddle API route tests (tasks 12.2 / 12.3 / 12.5).

Fully offline: the SDK call is monkeypatched where a URL is expected,
signatures are computed locally, and the ledger lives under ``tmp_path``
(``VANTIA_CREDITS_DIR``) so no test ever touches a real store or key.
"""

import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from engine.credits import CREDIT_PACKS, reset_default_ledger, reset_default_meter
from engine.credits.paddle_client import create_checkout_transaction
from engine.errors import PaddleError

SECRET = "pwl_api_test_secret"
CHECKOUT_URL = "https://sandbox.paddle.com/checkout/abc123"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path))
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", SECRET)
    monkeypatch.delenv("PADDLE_API_KEY", raising=False)
    monkeypatch.delenv("PADDLE_PRICE_PACK_10K", raising=False)
    reset_default_meter()
    reset_default_ledger()
    from engine.api import app

    with TestClient(app) as test_client:
        yield test_client
    reset_default_meter()
    reset_default_ledger()


def _event(event_id: str = "evt_api_1", event_type: str = "transaction.completed") -> bytes:
    return json.dumps(
        {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": "2026-10-09T00:00:00Z",
            "custom_data": {"user_id": "u-api", "pack_id": "pack_10k", "credits": "10000"},
        }
    ).encode()


def _sign(body: bytes) -> str:
    ts = str(int(time.time()))
    digest = hmac.new(SECRET.encode(), f"{ts}:{body.decode()}".encode(), hashlib.sha256).hexdigest()
    return f"ts={ts};h1={digest}"


# ── 12.2: POST /credits/checkout ──────────────────────────────────────


def test_checkout_requires_a_user_id(client):
    response = client.post("/credits/checkout", json={"pack_id": "pack_10k"})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "user_id_required"


def test_checkout_rejects_an_unknown_pack(client):
    response = client.post("/credits/checkout", json={"user_id": "u1", "pack_id": "pack_999k"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "unknown_pack"
    assert "pack_10k" in detail["message"]  # the known packs are listed


def test_checkout_returns_the_paddle_url_and_expected_credits(client, monkeypatch):
    captured: dict[str, str] = {}

    def fake_create(user_id: str, pack_id: str) -> str:
        captured["user_id"] = user_id
        captured["pack_id"] = pack_id
        return CHECKOUT_URL

    monkeypatch.setattr("engine.api.create_checkout_transaction", fake_create)
    response = client.post("/credits/checkout", json={"user_id": "u1", "pack_id": "pack_10k"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["checkout_url"] == CHECKOUT_URL
    assert body["pack_id"] == "pack_10k"
    assert body["credits"] == 10_000 == CREDIT_PACKS["pack_10k"]
    assert captured == {"user_id": "u1", "pack_id": "pack_10k"}


def test_checkout_config_failure_is_502_never_a_fake_url(client):
    """Unset Paddle keys must surface honestly, not fabricate a checkout."""
    response = client.post("/credits/checkout", json={"user_id": "u1", "pack_id": "pack_10k"})
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error"] == "paddle_error"
    assert "PADDLE_PRICE_PACK_10K" in detail["message"] or "PADDLE_API_KEY" in detail["message"]


def test_client_rejects_unknown_pack_before_touching_config(monkeypatch):
    monkeypatch.delenv("PADDLE_API_KEY", raising=False)
    with pytest.raises(PaddleError, match="unknown credit pack"):
        create_checkout_transaction("u1", "nope")


def test_client_names_the_missing_env_var(monkeypatch):
    monkeypatch.delenv("PADDLE_PRICE_PACK_50K", raising=False)
    monkeypatch.delenv("PADDLE_API_KEY", raising=False)
    with pytest.raises(PaddleError, match="PADDLE_PRICE_PACK_50K"):
        create_checkout_transaction("u1", "pack_50k")
    monkeypatch.setenv("PADDLE_PRICE_PACK_50K", "pri_test")
    with pytest.raises(PaddleError, match="PADDLE_API_KEY"):
        create_checkout_transaction("u1", "pack_50k")


def test_client_passes_custom_data_through_to_paddle(monkeypatch):
    """The webhook attributes top-ups from custom_data — pin its content."""
    monkeypatch.setenv("PADDLE_API_KEY", "pat_test")
    monkeypatch.setenv("PADDLE_PRICE_PACK_10K", "pri_test")
    captured: dict[str, object] = {}

    class _FakeTransactions:
        def create(self, op):
            captured["op"] = op
            return SimpleNamespace(checkout=SimpleNamespace(url=CHECKOUT_URL))

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.transactions = _FakeTransactions()

    monkeypatch.setattr("paddle_billing.Client", _FakeClient)
    url = create_checkout_transaction("u1", "pack_10k")
    assert url == CHECKOUT_URL
    op = captured["op"]
    # user_id / pack_id / credits must travel for webhook attribution
    assert "u1" in str(getattr(op, "custom_data", ""))
    assert "pack_10k" in str(getattr(op, "custom_data", ""))
    assert "10000" in str(getattr(op, "custom_data", ""))


# ── 12.5: GET /credits/packs ───────────────────────────────────────────


def test_packs_endpoint_exposes_priced_packs_for_the_ui(client):
    body = client.get("/credits/packs").json()
    packs = {p["id"]: p for p in body["packs"]}
    assert set(packs) == {"pack_10k", "pack_50k", "pack_250k"}
    assert packs["pack_10k"]["tokens"] == 10_000
    assert packs["pack_10k"]["price_usd"] == 5.0
    assert body["paddle_environment"] == "sandbox"
    assert body["ts"]


# ── 12.3: POST /paddle/webhook (route level) ───────────────────────────


def test_webhook_route_accepts_a_valid_signature_and_credits(client):
    from engine.credits import default_ledger

    body = _event()
    response = client.post(
        "/paddle/webhook", content=body, headers={"Paddle-Signature": _sign(body)}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "credited", "event_id": "evt_api_1", "ledger": "ok"}
    assert default_ledger().balance("u-api") == 10_000


def test_webhook_route_rejects_a_bad_signature_with_400(client):
    response = client.post(
        "/paddle/webhook", content=_event(), headers={"Paddle-Signature": "ts=1;h1=deadbeef"}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "paddle_error"


def test_webhook_route_redelivery_never_double_credits(client):
    from engine.credits import default_ledger

    body = _event(event_id="evt_api_dup")
    header = _sign(body)
    first = client.post("/paddle/webhook", content=body, headers={"Paddle-Signature": header})
    second = client.post("/paddle/webhook", content=body, headers={"Paddle-Signature": header})
    assert first.status_code == second.status_code == 200
    # No Supabase here → paddle_events dedupe is unavailable, but the ledger
    # ref idempotency still guarantees the money moves exactly once.
    assert default_ledger().balance("u-api") == 10_000
