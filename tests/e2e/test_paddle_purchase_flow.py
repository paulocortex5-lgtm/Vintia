"""End-to-end Paddle purchase test (task 12.6).

Offline purchase lifecycle: packs UI data → checkout URL (SDK patched) →
webhook delivery credits the ledger → the balance API shows the top-up →
the estimate reflects it → redelivery cannot double-credit → a
``payment_failed`` event records without crediting → a bad signature is
refused. Zero network: the SDK call is faked, signatures are computed
locally, and the ledger lives under ``tmp_path``.
"""

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from engine.credits import default_ledger, reset_default_ledger, reset_default_meter

SECRET = "pwl_e2e_purchase_secret"
USER = "user-purchase-1"
CHECKOUT_URL = "https://sandbox.paddle.com/checkout/e2e999"


def _event(
    event_id: str, event_type: str = "transaction.completed", credits: str = "50000"
) -> bytes:
    return json.dumps(
        {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": "2026-10-09T12:00:00Z",
            "custom_data": {"user_id": USER, "pack_id": "pack_50k", "credits": credits},
        }
    ).encode()


def _sign(body: bytes) -> str:
    ts = str(int(time.time()))
    digest = hmac.new(SECRET.encode(), f"{ts}:{body.decode()}".encode(), hashlib.sha256).hexdigest()
    return f"ts={ts};h1={digest}"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path))
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", SECRET)
    reset_default_meter()
    reset_default_ledger()
    from engine.api import app

    with TestClient(app) as test_client:
        yield test_client
    reset_default_meter()
    reset_default_ledger()


def test_full_purchase_journey_offline(client, monkeypatch):
    # 1. the purchase page gets its UI data (12.5)
    packs = client.get("/credits/packs").json()
    assert {p["id"] for p in packs["packs"]} == {"pack_10k", "pack_50k", "pack_250k"}
    assert packs["paddle_environment"] == "sandbox"

    # 2. checkout opens a Paddle URL (SDK faked — no network) (12.2)
    monkeypatch.setattr(
        "engine.api.create_checkout_transaction", lambda user_id, pack_id: CHECKOUT_URL
    )
    checkout = client.post(
        "/credits/checkout", json={"user_id": USER, "pack_id": "pack_50k"}
    ).json()
    assert checkout["checkout_url"] == CHECKOUT_URL
    assert checkout["pack_id"] == "pack_50k"
    assert checkout["credits"] == 50_000

    # 3. fresh free user starts with the monthly allowance (11.3/11.5)
    before = client.get("/credits/balance", params={"user_id": USER}).json()
    assert before["balance"] == 10_000
    assert before["tier"] == "free"

    # 4. Paddle delivers transaction.completed → credited once (12.3/12.4)
    body = _event("evt_purchase_1")
    response = client.post(
        "/paddle/webhook", content=body, headers={"Paddle-Signature": _sign(body)}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "credited",
        "event_id": "evt_purchase_1",
        "ledger": "ok",
    }
    assert default_ledger().balance(USER) == 60_000

    # 5. redelivery cannot double-credit (ledger ref idempotency)
    redeliver = client.post(
        "/paddle/webhook", content=body, headers={"Paddle-Signature": _sign(body)}
    )
    assert redeliver.status_code == 200
    assert default_ledger().balance(USER) == 60_000

    # 6. payment_failed records the event and credits nothing
    failed = _event("evt_purchase_fail", event_type="transaction.payment_failed")
    fail_response = client.post(
        "/paddle/webhook", content=failed, headers={"Paddle-Signature": _sign(failed)}
    )
    assert fail_response.json()["status"] == "recorded"
    assert fail_response.json()["ledger"] == "not_required"
    assert default_ledger().balance(USER) == 60_000

    # 7. a forged signature is refused with 400
    forged = client.post(
        "/paddle/webhook", content=body, headers={"Paddle-Signature": "ts=1;h1=beef"}
    )
    assert forged.status_code == 400

    # 8. the balance API tells the whole story (11.5)
    after = client.get("/credits/balance", params={"user_id": USER}).json()
    assert after["balance"] == 60_000
    assert [e["kind"] for e in after["recent_entries"]] == ["grant", "topup"]
    topup = after["recent_entries"][1]
    assert topup["ref"] == "paddle:evt_purchase_1"
    assert topup["meta"]["source"] == "paddle"

    # 9. the estimate reflects the purchased credits (read-only)
    estimate = client.get(
        "/credits/estimate", params={"user_id": USER, "operation": "cv_improvement"}
    ).json()
    assert estimate["affordable"] is True
    assert estimate["balance"] == estimate["available"] == 60_000
