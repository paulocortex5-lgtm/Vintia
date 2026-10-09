"""Credit API tests (task 11.5) — balance payload + read-only estimate.

Isolated per test: ``VANTIA_CREDITS_DIR`` points at ``tmp_path`` and both
singletons are reset (meter first — it captures the ledger at creation).
"""

import pytest
from fastapi.testclient import TestClient

from engine.credits import default_ledger, default_meter, reset_default_ledger, reset_default_meter


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path))
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    reset_default_meter()  # meter binds the ledger at creation — drop it first
    reset_default_ledger()
    from engine.api import app

    with TestClient(app) as test_client:
        yield test_client
    reset_default_meter()
    reset_default_ledger()


# ── GET /credits/balance (11.5) ────────────────────────────────────────


def test_balance_requires_a_user_id(client):
    response = client.get("/credits/balance")
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "user_id_required"


def test_fresh_user_sees_their_free_tier_allowance(client):
    response = client.get("/credits/balance", params={"user_id": "u1"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_id"] == "u1"
    assert body["balance"] == 10_000  # this month's allowance materialised
    assert body["tier"] == "free"
    assert body["monthly_allowance"] == 10_000
    assert body["allowance"] == {
        "granted": True,
        "month": body["allowance"]["month"],
        "amount": 10_000,
    }
    assert body["operations"]["cv_scan"] == 2_000
    assert {p["id"] for p in body["packs"]} == {"pack_10k", "pack_50k", "pack_250k"}
    assert body["entry_count"] == 1
    assert body["recent_entries"][0]["kind"] == "grant"
    assert body["ts"]


def test_balance_read_is_idempotent_across_calls(client):
    first = client.get("/credits/balance", params={"user_id": "u1"}).json()
    second = client.get("/credits/balance", params={"user_id": "u1"}).json()
    assert second["balance"] == first["balance"] == 10_000  # never double-granted
    assert second["allowance"]["granted"] is False  # already claimed this month
    assert first["allowance"]["granted"] is True


def test_balance_reflects_real_spending(client):
    client.get("/credits/balance", params={"user_id": "u1"})
    default_ledger().spend("u1", 2_000, "cv_scan:somewhere")
    body = client.get("/credits/balance", params={"user_id": "u1"}).json()
    assert body["balance"] == 8_000
    assert body["entry_count"] == 2
    assert [e["kind"] for e in body["recent_entries"]] == ["grant", "spend"]


# ── GET /credits/estimate (11.5) ───────────────────────────────────────


def test_estimate_validation_uses_stable_codes(client):
    assert client.get("/credits/estimate").status_code == 422
    missing_op = client.get("/credits/estimate", params={"user_id": "u1"})
    assert missing_op.json()["detail"]["error"] == "operation_required"
    unknown = client.get("/credits/estimate", params={"user_id": "u1", "operation": "teleport"})
    assert unknown.status_code == 422
    assert unknown.json()["detail"]["error"] == "unknown_operation"


def test_estimate_is_read_only_and_projects_the_allowance(client):
    body = client.get("/credits/estimate", params={"user_id": "u1", "operation": "cv_scan"}).json()
    assert body["cost"] == 2_000
    assert body["balance"] == 0  # nothing granted yet
    assert body["available"] == 10_000  # unclaimed allowance projected
    assert body["affordable"] is True
    # the read wrote nothing
    assert default_ledger().entries("u1") == []


def test_estimate_reports_a_real_shortfall(client):
    client.get("/credits/balance", params={"user_id": "u1"})  # grants 10 000
    default_ledger().spend("u1", 9_000, "drain")
    body = client.get(
        "/credits/estimate", params={"user_id": "u1", "operation": "cv_improvement"}
    ).json()
    assert body["balance"] == body["available"] == 1_000
    assert body["affordable"] is False
    assert body["shortfall"] == 7_000


def test_default_meter_reads_the_state_pricing(client):
    """API pricing comes from state.json, not a hardcoded table."""
    report = default_meter().estimate("u2", "cv_scan")
    assert report["cost"] == 2_000  # state credits.token_costs.cv_scan
