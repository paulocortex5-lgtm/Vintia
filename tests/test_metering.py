"""Metering + tiers tests (tasks 11.2 / 11.3) — pricing from config only.

No hardcoded prices: every test injects the config dict, exactly like a
deployment re-prices by editing ``state.json``.
"""

import pytest

from engine.credits.ledger import CreditLedger
from engine.credits.metering import CreditMeter, operation_cost
from engine.credits.tiers import (
    TIERS,
    enforce,
    ensure_allowance,
    projected_balance,
    set_tier,
    tier_of,
    tier_tokens,
)
from engine.errors import InsufficientCredits, VantiaError

CONFIG = {
    "free_tier_tokens": 10_000,
    "pro_tier_tokens": 100_000,
    "business_tier_tokens": 1_000_000,
    "token_costs": {"cv_scan": 2_000, "cv_improvement": 8_000, "cover_letter": 5_000},
}


@pytest.fixture()
def ledger(tmp_path):
    return CreditLedger(store_path=str(tmp_path / "ledger.json"))


# ── 11.2 pricing ───────────────────────────────────────────────────────


def test_operation_cost_reads_config():
    assert operation_cost("cv_scan", CONFIG) == 2_000
    assert operation_cost("cv_improvement", CONFIG) == 8_000
    assert operation_cost("cover_letter", CONFIG) == 5_000


def test_unknown_operation_refuses_with_known_list():
    with pytest.raises(VantiaError) as excinfo:
        operation_cost("teleport", CONFIG)
    assert excinfo.value.code == "unknown_operation"
    assert "cv_scan" in str(excinfo.value)
    assert excinfo.value.context["operation"] == "teleport"


def test_broken_prices_refuse_instead_of_defaulting_to_free():
    with pytest.raises(VantiaError) as e1:
        operation_cost("cv_scan", {"token_costs": {"cv_scan": "lots"}})
    assert e1.value.code == "operation_price_invalid"
    with pytest.raises(VantiaError) as e2:
        operation_cost("cv_scan", {"token_costs": {"cv_scan": -1}})
    assert e2.value.code == "operation_price_invalid"
    with pytest.raises(VantiaError) as e3:
        operation_cost("cv_scan", {})
    assert e3.value.code == "unknown_operation"


def test_config_loader_falls_back_to_the_packaged_seed():
    from engine.credits.config import load_credits_config

    cfg = load_credits_config(state_dir="/nonexistent/state")
    assert cfg["free_tier_tokens"] == 10_000  # seed values, not an error
    assert "cv_scan" in cfg["token_costs"]


def test_config_loader_returns_only_the_credits_block(tmp_path):
    import json

    from engine.credits.config import load_credits_config

    state = tmp_path / "state.json"
    state.write_text(json.dumps({"credits": {"token_costs": {"x": 1}}}), encoding="utf-8")
    assert load_credits_config(str(tmp_path)) == {"token_costs": {"x": 1}}


def test_env_vars_override_state_tiers(monkeypatch):
    """The .env.example VANTIA_* credit vars are honoured, not decorative."""
    from engine.credits.config import load_credits_config

    monkeypatch.setenv("VANTIA_FREE_TIER_TOKENS", "4242")
    monkeypatch.setenv("VANTIA_CREDITS_ENABLED", "false")
    cfg = load_credits_config(state_dir="/nonexistent/state")  # seed + overlay
    assert cfg["free_tier_tokens"] == 4242
    assert cfg["enabled"] is False
    assert cfg["pro_tier_tokens"] == 100_000  # untouched rows keep state/seed values


def test_invalid_env_override_fails_loudly(monkeypatch):
    from engine.credits.config import load_credits_config

    monkeypatch.setenv("VANTIA_FREE_TIER_TOKENS", "lots")
    with pytest.raises(VantiaError) as excinfo:
        load_credits_config(state_dir="/nonexistent/state")
    assert excinfo.value.code == "credits_config_invalid"
    assert excinfo.value.context["env"] == "VANTIA_FREE_TIER_TOKENS"


# ── 11.3 tiers ─────────────────────────────────────────────────────────


def test_tiers_are_the_three_documented_ones():
    assert TIERS == ("free", "pro", "business")
    assert tier_tokens("free", CONFIG) == 10_000
    assert tier_tokens("pro", CONFIG) == 100_000
    assert tier_tokens("business", CONFIG) == 1_000_000


def test_unknown_tier_refuses():
    with pytest.raises(VantiaError) as excinfo:
        tier_tokens("platinum", CONFIG)
    assert excinfo.value.code == "unknown_tier"


def test_tier_is_recorded_never_inferred(ledger):
    assert tier_of(ledger, "u1") == "free"  # default, not a guess
    set_tier(ledger, "u1", "pro")
    assert tier_of(ledger, "u1") == "pro"
    with pytest.raises(VantiaError) as excinfo:
        set_tier(ledger, "u2", "godmode")
    assert excinfo.value.code == "unknown_tier"
    assert tier_of(ledger, "u2") == "free"  # refused, not recorded


def test_allowance_grants_exactly_once_per_month(ledger):
    first = ensure_allowance(ledger, "u1", month="2026-10", config=CONFIG)
    assert first["granted"] is True
    assert first["amount"] == 10_000
    assert first["entry"]["ref"] == "allowance:u1:2026-10"

    second = ensure_allowance(ledger, "u1", month="2026-10", config=CONFIG)
    assert second["granted"] is False  # replay: no second credit
    assert ledger.balance("u1") == 10_000
    assert len(ledger.entries("u1")) == 1

    # next month is a new allowance (a new ref, not a double-credit)
    third = ensure_allowance(ledger, "u1", month="2026-11", config=CONFIG)
    assert third["granted"] is True
    assert ledger.balance("u1") == 20_000


def test_allowance_matches_the_recorded_tier(ledger):
    set_tier(ledger, "u1", "pro")
    result = ensure_allowance(ledger, "u1", month="2026-10", config=CONFIG)
    assert result["tier"] == "pro" and result["amount"] == 100_000
    assert ledger.balance("u1") == 100_000


def test_allowance_requires_a_user(ledger):
    with pytest.raises(VantiaError) as excinfo:
        ensure_allowance(ledger, "", config=CONFIG)
    assert excinfo.value.code == "user_id_required"


def test_enforce_refuses_below_cost_and_writes_nothing(ledger):
    ledger.topup("u1", 1_000, "t")
    assert enforce(ledger, "u1", required=1_000) == 1_000
    with pytest.raises(InsufficientCredits) as excinfo:
        enforce(ledger, "u1", required=5_000)
    assert excinfo.value.context == {"balance": 1_000, "required": 5_000}
    assert ledger.balance("u1") == 1_000
    with pytest.raises(VantiaError) as excinfo2:
        enforce(ledger, "u1", required=-1)
    assert excinfo2.value.code == "credits_required_invalid"


def test_projected_balance_counts_an_unclaimed_allowance_without_granting(ledger):
    assert projected_balance(ledger, "fresh", config=CONFIG) == 10_000
    assert ledger.entries("fresh") == []  # projection wrote nothing

    ensure_allowance(ledger, "fresh", month="2026-10", config=CONFIG)
    ledger.spend("fresh", 4_000, "s")
    # allowance already claimed → projection == literal balance
    assert projected_balance(ledger, "fresh", month="2026-10", config=CONFIG) == 6_000
    assert ledger.balance("fresh") == 6_000


# ── CreditMeter middleware (11.2 → 11.4 contract) ──────────────────────


def test_estimate_separates_real_balance_from_available(ledger):
    meter = CreditMeter(ledger, config=CONFIG)
    report = meter.estimate("u1", "cv_scan")
    assert report["cost"] == 2_000
    assert report["balance"] == 0  # literal ledger balance
    assert report["available"] == 10_000  # incl. unclaimed allowance
    assert report["affordable"] is True
    assert report["shortfall"] == 0


def test_preflight_grants_allowance_then_enforces(ledger):
    meter = CreditMeter(ledger, config=CONFIG)
    plan = meter.preflight("u1", "cv_scan")
    assert plan["cost"] == 2_000
    assert plan["balance_after_allowance"] == 10_000
    assert plan["tier"] == "free"
    assert plan["monthly_allowance"] == 10_000
    assert meter.ledger.balance("u1") == 10_000  # allowance materialised

    ledger.spend("u1", 9_000, "drain")  # 1 000 left < 8 000 needed
    with pytest.raises(InsufficientCredits):
        meter.preflight("u1", "cv_improvement")
    assert ledger.balance("u1") == 1_000  # refusal moved nothing


def test_charge_is_idempotent_by_ref(ledger):
    meter = CreditMeter(ledger, config=CONFIG)
    ensure_allowance(ledger, "u1", config=CONFIG)
    first = meter.charge("u1", "cv_scan", "scan:ref-2")
    replay = meter.charge("u1", "cv_scan", "scan:ref-2")
    assert first == replay
    assert first["cost"] == 2_000
    assert first["balance_after"] == 8_000
    assert [e["ref"] for e in ledger.entries("u1")].count("scan:ref-2") == 1

    # a charge beyond the balance is still R46-refused (belt and braces)
    ledger.spend("u1", 8_000, "drain")
    with pytest.raises(InsufficientCredits):
        meter.charge("u1", "cv_improvement", "no-funds")
    assert ledger.balance("u1") == 0


def test_metered_charges_only_on_success(ledger):
    meter = CreditMeter(ledger, config=CONFIG)
    with meter.metered("u1", "cv_scan", "run:1") as plan:
        assert plan["cost"] == 2_000
    assert ledger.balance("u1") == 8_000  # success → charged

    with pytest.raises(RuntimeError), meter.metered("u1", "cv_scan", "run:2"):
        raise RuntimeError("work failed")
    assert ledger.balance("u1") == 8_000  # failure → nothing charged
    assert [e["ref"] for e in ledger.entries("u1")].count("run:2") == 0


def test_metered_refuses_before_the_body_runs_when_broke(ledger):
    meter = CreditMeter(ledger, config=CONFIG)
    ensure_allowance(ledger, "u1", config=CONFIG)
    ledger.spend("u1", 9_500, "drain")  # 500 left
    ran = False
    with pytest.raises(InsufficientCredits), meter.metered("u1", "cv_improvement", "run:3"):
        ran = True
    assert ran is False  # refused before any work started
    assert ledger.balance("u1") == 500
