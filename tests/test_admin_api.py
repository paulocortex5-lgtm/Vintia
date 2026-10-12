"""Admin API tests (hidden /admin panel) — fail-closed auth + settings.

Isolation per test: ``VANTIA_CREDITS_DIR`` → ``tmp_path`` (ledger),
CWD → ``tmp_path`` (state), both singletons reset, and the admin token
plus every env override is controlled by ``monkeypatch``. The guard is
probed first: unconfigured → 503, missing header → 401, wrong key → 403
— the admin surface must never be reachable by accident.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.credits import reset_default_ledger, reset_default_meter

ADMIN_TOKEN = "test-admin-token-3f9a"
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

#: Env vars that must not leak in from the developer shell.
TIER_ENV = ("VANTIA_FREE_TIER_TOKENS", "VANTIA_PRO_TIER_TOKENS", "VANTIA_BUSINESS_TIER_TOKENS")
PAID_ENV = (
    "VANTIA_FLAG_PAID_LLM",
    "VANTIA_ALLOW_PAID_LLM",
    "VANTIA_FLAG_INVOICE_GENERATION",
    "VANTIA_FLAG_WORKSPACE_UI",
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path / "credits"))
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    monkeypatch.setenv("VANTIA_ADMIN_TOKEN", ADMIN_TOKEN)
    for name in TIER_ENV + PAID_ENV:
        monkeypatch.delenv(name, raising=False)
    reset_default_meter()  # meter binds the ledger at creation — drop it first
    reset_default_ledger()
    from engine.api import app

    with TestClient(app) as test_client:
        yield test_client
    reset_default_meter()
    reset_default_ledger()


# ── Auth: fail-closed, never "open because unset" ──────────────────────


def test_unconfigured_token_closes_every_admin_route(client, monkeypatch):
    monkeypatch.delenv("VANTIA_ADMIN_TOKEN")
    probes = [
        client.get("/admin/overview", headers=AUTH),
        client.get("/admin/credits", params={"user_id": "u1"}, headers=AUTH),
        client.put("/admin/tiers", json={"free_tier_tokens": 1}, headers=AUTH),
        client.post("/admin/usage-tier", json={"enabled": True}, headers=AUTH),
        client.post("/admin/credits/grant", json={"user_id": "u1", "amount": 1}, headers=AUTH),
        client.post("/admin/users/tier", json={"user_id": "u1", "tier": "pro"}, headers=AUTH),
    ]
    for response in probes:
        assert response.status_code == 503, response.text
        assert response.json()["detail"]["error"] == "admin_not_configured"


def test_missing_bearer_header_is_401(client):
    response = client.get("/admin/overview")
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "missing_token"


def test_malformed_authorization_is_401(client):
    response = client.get("/admin/overview", headers={"Authorization": ADMIN_TOKEN})
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "missing_token"


def test_wrong_token_is_403_and_changes_nothing(client):
    response = client.get("/admin/overview", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 403


# ── GET /admin/overview ────────────────────────────────────────────────


def test_overview_returns_tiers_flags_and_ledger(client):
    response = client.get("/admin/overview", headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body["flags"]) == {"paid_llm", "invoice_generation", "workspace_ui"}
    assert body["flags"]["paid_llm"] is False  # seed default
    assert set(body["tiers"]) == {"free", "pro", "business"}
    assert body["tiers"]["free"]["tokens"] == 10_000
    assert body["tiers"]["pro"]["tokens"] == 100_000
    assert body["tiers"]["business"]["tokens"] == 1_000_000
    assert body["paid_usage"]["enabled"] is False
    assert body["ledger"]["user_count"] == 0
    assert body["ts"]


def test_overview_reports_env_overrides_that_mask_state(client, monkeypatch):
    monkeypatch.setenv("VANTIA_FREE_TIER_TOKENS", "42")
    body = client.get("/admin/overview", headers=AUTH).json()
    assert body["tiers"]["free"]["tokens"] == 42  # effective (env wins)
    assert body["tiers"]["free"]["state_tokens"] == 10_000  # raw state, honest
    assert [m["env"] for m in body["tiers"]["free"]["env_override"]] == ["VANTIA_FREE_TIER_TOKENS"]


# ── PUT /admin/tiers ───────────────────────────────────────────────────


def test_tier_allowances_persist_to_state(client):
    response = client.put(
        "/admin/tiers", json={"free_tier_tokens": 5_000, "pro_tier_tokens": 50_000}, headers=AUTH
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tiers"]["free"]["tokens"] == 5_000
    assert body["tiers"]["pro"]["tokens"] == 50_000
    assert body["tiers"]["business"]["tokens"] == 1_000_000  # untouched
    # the write is really on disk (state.json), not just in the response
    state = json.loads(Path(".vantia/state/state.json").read_text(encoding="utf-8"))
    assert state["credits"]["free_tier_tokens"] == 5_000
    # and the public credit routes see the new allowance too
    balance = client.get("/credits/balance", params={"user_id": "u1"}).json()
    assert balance["balance"] == 5_000
    assert balance["monthly_allowance"] == 5_000


def test_tier_update_validates_inputs(client):
    empty = client.put("/admin/tiers", json={}, headers=AUTH)
    assert empty.status_code == 422
    assert empty.json()["detail"]["error"] == "tier_tokens_invalid"
    negative = client.put("/admin/tiers", json={"free_tier_tokens": -1}, headers=AUTH)
    assert negative.status_code == 422
    assert negative.json()["detail"]["error"] == "tier_tokens_invalid"
    zero = client.put("/admin/tiers", json={"free_tier_tokens": 0}, headers=AUTH)
    assert zero.status_code == 422


def test_tier_update_reports_env_masking_the_new_value(client, monkeypatch):
    monkeypatch.setenv("VANTIA_PRO_TIER_TOKENS", "777")
    body = client.put("/admin/tiers", json={"pro_tier_tokens": 123}, headers=AUTH).json()
    assert body["tiers"]["pro"]["state_tokens"] == 123  # stored
    assert body["tiers"]["pro"]["tokens"] == 777  # effective (env wins)
    assert [m["env"] for m in body["tiers"]["pro"]["env_override"]] == ["VANTIA_PRO_TIER_TOKENS"]


# ── POST /admin/usage-tier (paid usage switch) ─────────────────────────


def test_paid_usage_switch_flips_state_and_flag(client):
    on = client.post("/admin/usage-tier", json={"enabled": True}, headers=AUTH)
    assert on.status_code == 200, on.text
    assert on.json()["enabled"] is True
    assert on.json()["effective_flag"] is True  # paid_llm flag follows state
    off = client.post("/admin/usage-tier", json={"enabled": False}, headers=AUTH)
    assert off.json()["enabled"] is False
    assert off.json()["effective_flag"] is False
    # persisted on disk
    state = json.loads(Path(".vantia/state/state.json").read_text(encoding="utf-8"))
    assert state["llm_policy"]["allow_paid"] is False


def test_paid_usage_switch_reports_env_override(client, monkeypatch):
    monkeypatch.setenv("VANTIA_FLAG_PAID_LLM", "0")
    body = client.post("/admin/usage-tier", json={"enabled": True}, headers=AUTH).json()
    assert body["enabled"] is True  # stored in state
    assert body["effective_flag"] is False  # env override wins — reported, not hidden
    assert [m["env"] for m in body["env_override"]] == ["VANTIA_FLAG_PAID_LLM"]


# ── Credits management (grant/adjust + per-user tier) ──────────────────


def test_grant_and_adjust_credits_through_the_ledger(client):
    grant = client.post(
        "/admin/credits/grant",
        json={"user_id": "u1", "amount": 5_000, "note": "goodwill"},
        headers=AUTH,
    )
    assert grant.status_code == 200, grant.text
    body = grant.json()
    assert body["balance"] == 5_000
    assert body["entry"]["kind"] == "grant"
    assert body["entry"]["meta"]["source"] == "admin"
    assert body["entry"]["meta"]["note"] == "goodwill"

    adjust = client.post(
        "/admin/credits/grant", json={"user_id": "u1", "amount": -1_500}, headers=AUTH
    )
    assert adjust.status_code == 200, adjust.text
    assert adjust.json()["balance"] == 3_500
    assert adjust.json()["entry"]["kind"] == "adjustment"


def test_grant_is_idempotent_by_ref(client):
    payload = {"user_id": "u1", "amount": 1_000, "ref": "promo:2026-10"}
    first = client.post("/admin/credits/grant", json=payload, headers=AUTH)
    second = client.post("/admin/credits/grant", json=payload, headers=AUTH)
    assert first.json()["balance"] == 1_000
    assert second.json()["balance"] == 1_000  # replay moves no money


def test_adjustment_cannot_drive_balance_below_zero(client):
    client.post("/admin/credits/grant", json={"user_id": "u1", "amount": 100}, headers=AUTH)
    response = client.post(
        "/admin/credits/grant", json={"user_id": "u1", "amount": -5_000}, headers=AUTH
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "insufficient_credits"
    # R46: nothing moved
    view = client.get("/admin/credits", params={"user_id": "u1"}, headers=AUTH).json()
    assert view["balance"] == 100


def test_admin_credits_view_and_user_tier(client):
    client.post("/admin/credits/grant", json={"user_id": "u1", "amount": 500}, headers=AUTH)
    view = client.get("/admin/credits", params={"user_id": "u1"}, headers=AUTH)
    assert view.status_code == 200, view.text
    body = view.json()
    assert body["balance"] == 500
    assert body["tier"] == "free"  # recorded, never guessed
    assert body["monthly_allowance"] == 10_000
    assert body["recent_entries"][-1]["kind"] == "grant"

    tier = client.post("/admin/users/tier", json={"user_id": "u1", "tier": "pro"}, headers=AUTH)
    assert tier.status_code == 200, tier.text
    assert tier.json()["tier"] == "pro"
    assert tier.json()["monthly_allowance"] == 100_000


def test_unknown_user_tier_is_refused(client):
    response = client.post(
        "/admin/users/tier", json={"user_id": "u1", "tier": "platinum"}, headers=AUTH
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "unknown_tier"


def test_admin_credits_requires_user_id(client):
    assert client.get("/admin/credits", headers=AUTH).status_code == 422
    missing = client.post("/admin/credits/grant", json={"amount": 1}, headers=AUTH)
    assert missing.status_code == 422
    assert missing.json()["detail"]["error"] == "user_id_required"


def test_zero_amount_grant_is_refused(client):
    response = client.post(
        "/admin/credits/grant", json={"user_id": "u1", "amount": 0}, headers=AUTH
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "ledger_amount_invalid"
