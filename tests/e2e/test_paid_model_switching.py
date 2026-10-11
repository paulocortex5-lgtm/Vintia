"""End-to-end paid-model switching tests (task 7.3).

The free → paid toggle end to end: router profiles honour
``allow_paid`` (R27 free-before-paid), feature flags resolve from state
with loud env overrides, tier switches move allowances exactly once per
month, and credit statements (invoices) are deterministic, offline and
denied when the flag is off. Zero network.
"""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from engine.credits import (
    default_ledger,
    ensure_allowance,
    generate_invoice,
    reset_default_ledger,
    reset_default_meter,
    set_tier,
)
from engine.errors import AllProvidersExhausted, VantiaError
from engine.feature_flags import KNOWN_FLAGS, flags, is_enabled
from engine.llm.client import LLMClient
from engine.llm.quota import QuotaTracker
from engine.llm.router import pick

MSGS = [{"role": "user", "content": "hello"}]

OK_BODY = {
    "id": "gen-paid",
    "choices": [{"message": {"content": "served"}}],
    "usage": {"prompt_tokens": 5, "completion_tokens": 7},
}

# Both a free key (groq) and a paid key (openai) exist — the router must
# still decide purely by profile + toggle, never by key presence alone.
ENV_WITH_BOTH_KEYS = {"GROQ_API_KEY": "gsk_test", "OPENAI_API_KEY": "sk_test"}


def quota(tmp_path) -> QuotaTracker:
    return QuotaTracker(cache_dir=tmp_path / "quota")


def chain_ids(chain) -> list[str]:
    return [p.id for p in chain]


# ── 1. free_only never touches a paid provider, keys or not ───────────────


def test_free_only_profile_never_selects_a_paid_provider(tmp_path):
    chain = pick(
        profile="free_only",
        environ={**ENV_WITH_BOTH_KEYS, "VANTIA_ALLOW_PAID_LLM": "1"},
        quota_tracker=quota(tmp_path),
    )
    assert chain, "free providers with keys must form a chain"
    assert all(p.tier == "free" for p in chain)
    assert "openai" not in chain_ids(chain)


# ── 2. the paid profile honours the toggle, free first (R27) ──────────────


def test_paid_profile_honours_the_toggle_with_free_providers_first(tmp_path):
    blocked = pick(
        profile="paid",
        environ=ENV_WITH_BOTH_KEYS,
        quota_tracker=quota(tmp_path),
        allow_paid=False,
    )
    assert blocked and all(p.tier == "free" for p in blocked)

    allowed = pick(
        profile="paid",
        environ=ENV_WITH_BOTH_KEYS,
        quota_tracker=quota(tmp_path),
        allow_paid=True,
    )
    tiers = [p.tier for p in allowed]
    assert "paid" in tiers
    # R27: every free provider precedes every paid one.
    first_paid = tiers.index("paid")
    assert all(t == "free" for t in tiers[:first_paid])


# ── 3. failover only falls into paid when the toggle allows it ────────────


def paid_failing_transport(request: httpx.Request) -> httpx.Response:
    if request.url.host == "api.groq.com":
        return httpx.Response(429, text="free quota spent")
    return httpx.Response(200, json=OK_BODY)  # the paid provider answers


def test_free_exhaustion_falls_to_paid_only_when_allowed(tmp_path):
    tracker = quota(tmp_path)
    free_chain = pick(
        profile="paid", environ=ENV_WITH_BOTH_KEYS, quota_tracker=tracker, allow_paid=False
    )
    client = LLMClient(
        http_client=httpx.Client(transport=httpx.MockTransport(paid_failing_transport))
    )
    # Toggle off: the exhausted free chain must NOT silently go paid.
    with pytest.raises(AllProvidersExhausted):
        client.run_chain([(p, p.default_model) for p in free_chain], MSGS)

    # Toggle on: the same failure now falls through to the paid provider.
    full_chain = pick(
        profile="paid", environ=ENV_WITH_BOTH_KEYS, quota_tracker=tracker, allow_paid=True
    )
    result = client.run_chain([(p, p.default_model) for p in full_chain], MSGS)
    assert result.text == "served"
    assert result.provider != "groq"  # groq was rate-limited; paid served


# ── 4. feature flags: state-driven, env-overridden, fail closed ───────────


def write_state(state_dir: Path, block: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "state.json").write_text(json.dumps(block), encoding="utf-8")


def test_flags_resolve_from_state_and_fail_closed_on_unknowns(tmp_path):
    write_state(
        tmp_path,
        {
            "llm_policy": {"allow_paid": False},
            "credits": {"enabled": True},
            "workspaces": {"enabled": True},
        },
    )
    resolved = flags(state_dir=str(tmp_path), environ={})
    assert resolved == {"paid_llm": False, "invoice_generation": True, "workspace_ui": True}

    # Env override flips one flag without touching the others.
    flipped = flags(state_dir=str(tmp_path), environ={"VANTIA_FLAG_PAID_LLM": "1"})
    assert flipped["paid_llm"] is True
    assert flipped["invoice_generation"] is True

    # Unknown flags are off — a typo never switches a feature on.
    assert is_enabled("definitely_not_a_flag", state_dir=str(tmp_path), environ={}) is False
    assert set(KNOWN_FLAGS) == {"paid_llm", "invoice_generation", "workspace_ui"}


def test_invalid_flag_value_raises_instead_of_guessing(tmp_path):
    write_state(tmp_path, {"llm_policy": {"allow_paid": False}})
    with pytest.raises(VantiaError) as excinfo:
        flags(state_dir=str(tmp_path), environ={"VANTIA_FLAG_PAID_LLM": "maybe"})
    assert excinfo.value.code == "flag_value_invalid"


# ── 5. tier switching: allowance once per month, tier recorded not guessed ─


@pytest.fixture()
def offline_credits(tmp_path, monkeypatch):
    """Hermetic ledger + meter, pointed at tmp (never the repo store)."""
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path / "credits"))
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    reset_default_meter()
    reset_default_ledger()
    return tmp_path


def test_free_to_pro_switch_moves_the_allowance_exactly_once(offline_credits):
    user = "u-tier"
    ledger = default_ledger()

    free = ensure_allowance(user_id=user, month="2026-10")
    assert free["granted"] is True and free["tier"] == "free"
    assert free["amount"] == 10_000  # state free_tier_tokens

    # Mid-month upgrade: tier is recorded; the month's allowance does not move.
    set_tier(ledger, user, "pro")
    repeat = ensure_allowance(user_id=user, month="2026-10")
    assert repeat["granted"] is False
    assert ledger.balance(user) == 10_000

    # Next month the pro allowance lands, exactly once.
    pro = ensure_allowance(user_id=user, month="2026-11")
    assert pro["granted"] is True and pro["tier"] == "pro"
    assert pro["amount"] == 100_000  # state pro_tier_tokens
    again = ensure_allowance(user_id=user, month="2026-11")
    assert again["granted"] is False
    assert ledger.balance(user) == 110_000


# ── 6. credit statements: deterministic, offline, flag-gated ──────────────


def test_invoice_is_deterministic_offline_and_denied_when_flag_off(offline_credits):
    user = "u-invoice"
    ledger = default_ledger()
    ledger.topup(user, 5_000, ref="pack_10k")
    ledger.spend(user, 2_000, ref="cv_scan:r1")

    first = generate_invoice(user, ledger=ledger, environ={})
    second = generate_invoice(user, ledger=ledger, environ={})
    assert first == second  # same ledger + period → identical document
    assert first["unit"] == "credits"  # never an invented currency
    assert first["total_earned"] == 5_000
    assert first["total_spent"] == 2_000
    assert first["net"] == 3_000
    assert first["balance"] == 3_000
    assert [line["ref"] for line in first["lines"]] == ["pack_10k", "cv_scan:r1"]
    assert "usd" not in json.dumps(first).lower()

    with pytest.raises(VantiaError) as excinfo:
        generate_invoice(user, ledger=ledger, environ={"VANTIA_FLAG_INVOICE_GENERATION": "0"})
    assert excinfo.value.code == "invoice_generation_disabled"


def test_invoice_api_matches_the_module_and_gates_honestly(offline_credits, monkeypatch):
    from engine.api import app

    user = "u-invoice-api"
    ledger = default_ledger()
    ledger.topup(user, 3_000, ref="pack_10k")

    client = TestClient(app)
    response = client.get("/credits/invoices", params={"user_id": user})
    assert response.status_code == 200
    body = response.json()
    assert body.pop("ts")  # wall-clock provenance, not part of the document
    assert body == generate_invoice(user, month=body["period"], ledger=ledger, environ={})

    # Stable failure shapes.
    assert client.get("/credits/invoices").status_code == 422  # user_id_required
    bad_period = client.get("/credits/invoices", params={"user_id": user, "month": "2026-13"})
    assert bad_period.status_code == 422
    assert bad_period.json()["detail"]["error"] == "invoice_period_invalid"

    monkeypatch.setenv("VANTIA_FLAG_INVOICE_GENERATION", "0")
    flagged = client.get("/credits/invoices", params={"user_id": user})
    assert flagged.status_code == 403
    assert flagged.json()["detail"]["error"] == "invoice_generation_disabled"


if __name__ == "__main__":  # pragma: no cover — direct-run convenience
    pytest.main([__file__, "-v"])
