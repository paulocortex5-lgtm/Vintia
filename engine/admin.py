"""Admin service for the hidden ``/admin`` panel (settings, tiers, credits).

The panel itself is never linked from the UI (invoked only by typing
``/admin``); the *API* behind it is fail-closed and honours the repo's
honesty rules:

* **Fail-closed auth** — every entry point calls :func:`require_admin`
  first: without a configured ``VANTIA_ADMIN_TOKEN`` the answer is
  ``admin_not_configured`` (503), never "open because unset". The token
  is compared with :func:`hmac.compare_digest` (constant time) and a
  mismatch is ``admin_forbidden`` (403).
* **State is authoritative** — tier allowances and the paid-usage switch
  are written into ``state.json`` through the same guarded
  :class:`~engine.state_manager.VantiaState` save the CLI uses (lock,
  atomic write). Env overlays (``VANTIA_*_TIER_TOKENS``,
  ``VANTIA_FLAG_PAID_LLM``, ``VANTIA_ALLOW_PAID_LLM``) still win at read
  time (12-factor), so every response reports which env var — if any —
  masks the state value the admin just wrote. A shadowed write is
  reported loudly, never silently ignored.
* **Credits move only through the ledger** — grants/adjustments are
  append-only entries idempotent by ``ref``; R46 still applies: an
  adjustment that would drive the balance below zero writes nothing.
* **Tier is recorded, never inferred** — per-user tier changes go
  through :func:`engine.credits.tiers.set_tier` with validation.
"""

from __future__ import annotations

import hmac
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from .credits import (
    TIERS,
    default_ledger,
    load_credits_config,
    set_tier,
    tier_of,
    tier_tokens,
)
from .errors import StateLockBusy, VantiaError
from .feature_flags import KNOWN_FLAGS
from .feature_flags import flags as feature_flags
from .json_utils import load_json
from .state_manager import DEFAULT_STATE_DIR, VantiaState, seed_path

__all__ = [
    "admin_overview",
    "grant_credits",
    "require_admin",
    "set_paid_usage",
    "set_tier_allowances",
    "set_user_tier",
    "user_credits",
]

_PLACEHOLDER = "REPLACE_ME"

#: state path → the env var that overrides it (honesty reporting).
TIER_ENV_OVERRIDES = {
    "free_tier_tokens": "VANTIA_FREE_TIER_TOKENS",
    "pro_tier_tokens": "VANTIA_PRO_TIER_TOKENS",
    "business_tier_tokens": "VANTIA_BUSINESS_TIER_TOKENS",
}

#: env vars that override the paid-usage switch.
PAID_ENV_OVERRIDES = ("VANTIA_FLAG_PAID_LLM", "VANTIA_ALLOW_PAID_LLM")


def require_admin(authorization: str | None) -> None:
    """Guard every admin entry point (fail-closed, constant-time).

    Raises :class:`~engine.errors.VantiaError` codes the API maps to:
    ``admin_not_configured`` (503 — the token env var is unset or a
    placeholder), ``missing_token`` (401 — no ``Bearer`` header) and
    ``admin_forbidden`` (403 — wrong token).
    """
    configured = os.environ.get("VANTIA_ADMIN_TOKEN", "")
    if not configured or configured == _PLACEHOLDER:
        raise VantiaError(
            "VANTIA_ADMIN_TOKEN is not configured; the admin API stays closed",
            code="admin_not_configured",
        )
    if not authorization:
        raise VantiaError("Authorization header is missing", code="missing_token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise VantiaError("Authorization must be 'Bearer <token>'", code="missing_token")
    if not hmac.compare_digest(token.strip(), configured):
        raise VantiaError("admin token rejected", code="admin_forbidden")


def _state(state_dir: str | None) -> VantiaState:
    return VantiaState(state_dir or DEFAULT_STATE_DIR)


def _locked_write(state: VantiaState, mutate: Any) -> dict[str, Any]:
    """Acquire the run lock, apply ``mutate(data)``, save atomically.

    A missing state file is materialised from the packaged seed first
    (§0.1 STEP A) so admin writes work on a fresh deployment instead of
    failing with ``state_error``.
    """
    lock = state.lock()
    if not lock.acquire(owner="admin"):
        raise StateLockBusy("state lock is held by another run; retry shortly")
    try:
        if not state.exists:
            state.first_run()
        data = state.load()
        mutate(data)
        return state.save(data)
    finally:
        lock.release()


def _read_state(state: VantiaState) -> dict[str, Any]:
    """Raw state dict; packaged seed when the file is absent (never invent)."""
    try:
        data = state.load()
    except Exception:  # noqa: BLE001 — missing/corrupt state falls back to the seed
        data = load_json(seed_path())
    return data if isinstance(data, dict) else {}


def _env_mask(env_names: tuple[str, ...] | list[str], state_value: Any) -> list[dict[str, Any]]:
    """Env vars currently set that override ``state_value`` (honesty)."""
    masked = []
    for name in env_names:
        raw = os.environ.get(name)
        if raw not in (None, ""):
            masked.append({"env": name, "value": raw, "state_value": state_value})
    return masked


def admin_overview(*, state_dir: str | None = None) -> dict[str, Any]:
    """Everything the /admin panel renders on load (read-only).

    Includes the resolved feature flags, per-tier allowances with any
    masking env vars, the paid-usage switch (state + effective env), and
    a ledger rollup — no secrets, no invented numbers.
    """
    config = load_credits_config(state_dir)
    ledger = default_ledger()
    data = _read_state(_state(state_dir))
    raw_policy = data.get("llm_policy")
    policy: dict[str, Any] = raw_policy if isinstance(raw_policy, dict) else {}
    raw_credits_block = data.get("credits")
    raw_credits: dict[str, Any] = raw_credits_block if isinstance(raw_credits_block, dict) else {}
    resolved = feature_flags(state_dir=state_dir)

    tiers = {}
    for tier in TIERS:
        key = f"{tier}_tier_tokens"
        env_name = TIER_ENV_OVERRIDES[key]
        raw = os.environ.get(env_name)
        tiers[tier] = {
            "tokens": tier_tokens(tier, config),  # effective (env overlay wins)
            "state_tokens": raw_credits.get(key),  # raw state value
            "env_override": _env_mask([env_name], raw_credits.get(key)),
            "env_value": raw if raw not in (None, "") else None,
        }

    return {
        "flags": {name: bool(resolved.get(name)) for name in KNOWN_FLAGS},
        "flags_env": _env_mask([f"VANTIA_FLAG_{name.upper()}" for name in KNOWN_FLAGS], None),
        "tiers": tiers,
        "credits_enabled": bool(config.get("enabled")),
        "token_costs": dict(config.get("token_costs") or {}),
        "paid_usage": {
            "enabled": bool(policy.get("allow_paid")),
            "profile": str(policy.get("profile") or ""),
            "env_override": _env_mask(PAID_ENV_OVERRIDES, policy.get("allow_paid")),
        },
        "ledger": ledger.rollup(),
        "ts": datetime.now(UTC).isoformat(),
    }


def set_tier_allowances(updates: dict[str, int], *, state_dir: str | None = None) -> dict[str, Any]:
    """Persist per-tier monthly token allowances into state (§4).

    ``updates`` maps ``<tier>_tier_tokens`` → positive int. Unknown keys
    are refused (``unknown_tier``), non-positive values are refused
    (``tier_tokens_invalid``). Returns the tiers after the write plus the
    env vars that mask them, so the panel can warn honestly.
    """
    cleaned: dict[str, int] = {}
    for key, value in updates.items():
        if key not in TIER_ENV_OVERRIDES:
            raise VantiaError(
                f"unknown tier setting {key!r}; known: {', '.join(sorted(TIER_ENV_OVERRIDES))}",
                code="unknown_tier",
            )
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise VantiaError(
                f"{key} must be a whole number of tokens", code="tier_tokens_invalid"
            ) from exc
        if parsed <= 0:
            raise VantiaError(
                f"{key} must be a positive number of tokens", code="tier_tokens_invalid"
            )
        cleaned[key] = parsed
    if not cleaned:
        raise VantiaError("no tier settings supplied", code="tier_tokens_invalid")

    state = _state(state_dir)

    def mutate(data: dict[str, Any]) -> None:
        credits = data.setdefault("credits", {})
        for key, value in cleaned.items():
            credits[key] = value

    _locked_write(state, mutate)
    config = load_credits_config(state_dir)
    raw_credits = _read_state(state).get("credits", {})
    return {
        "tiers": {
            tier: {
                "tokens": tier_tokens(tier, config),  # effective (env overlay wins)
                "state_tokens": raw_credits.get(f"{tier}_tier_tokens"),  # raw state
                "env_override": _env_mask(
                    [TIER_ENV_OVERRIDES[f"{tier}_tier_tokens"]],
                    raw_credits.get(f"{tier}_tier_tokens"),
                ),
            }
            for tier in TIERS
        },
        "applied": sorted(cleaned),
        "ts": datetime.now(UTC).isoformat(),
    }


def set_paid_usage(enabled: bool, *, state_dir: str | None = None) -> dict[str, Any]:
    """Switch the platform between the free and paid usage tiers (§17).

    Writes ``llm_policy.allow_paid`` in state under the run lock. The
    response reports the stored value *and* any env var that currently
    masks it (``VANTIA_FLAG_PAID_LLM`` for the feature flag,
    ``VANTIA_ALLOW_PAID_LLM`` for the router) — an admin must never
    believe a switch took effect when the environment says otherwise.
    """
    state = _state(state_dir)

    def mutate(data: dict[str, Any]) -> None:
        policy = data.setdefault("llm_policy", {})
        if not isinstance(policy, dict):  # hand-edited garbage → loud, not a wipe
            raise VantiaError(
                "state llm_policy is not an object; refusing to overwrite",
                code="state_invalid",
            )
        policy["allow_paid"] = bool(enabled)

    _locked_write(state, mutate)
    resolved = feature_flags(state_dir=state_dir)
    data = state.load()
    block = data.get("llm_policy")
    policy_out: dict[str, Any] = block if isinstance(block, dict) else {}
    return {
        "enabled": bool(policy_out.get("allow_paid")),
        "effective_flag": bool(resolved.get("paid_llm")),
        "env_override": _env_mask(PAID_ENV_OVERRIDES, policy_out.get("allow_paid")),
        "ts": datetime.now(UTC).isoformat(),
    }


def set_user_tier(user_id: str, tier: str, *, state_dir: str | None = None) -> dict[str, Any]:
    """Record ``tier`` for ``user_id`` (validated free/pro/business)."""
    if not user_id:
        raise VantiaError("user_id is required", code="user_id_required")
    ledger = default_ledger()
    stored = set_tier(ledger, user_id, tier)  # validates, raises unknown_tier
    config = load_credits_config(state_dir)
    return {
        "user_id": user_id,
        "tier": stored,
        "monthly_allowance": tier_tokens(stored, config),
        "ts": datetime.now(UTC).isoformat(),
    }


def grant_credits(
    user_id: str,
    amount: int,
    *,
    note: str = "",
    ref: str = "",
    state_dir: str | None = None,
) -> dict[str, Any]:
    """Grant (+) or adjust (−) credits for ``user_id`` via the ledger.

    Idempotent by ``ref`` (auto-generated when absent): replaying the
    same ref moves no money. R46 still holds — a negative adjustment
    that would drop the balance below zero raises ``insufficient_credits``
    and writes nothing. ``kind`` is ``grant`` for positive amounts,
    ``adjustment`` for negative ones (both in ``ENTRY_KINDS``).
    """
    if not user_id:
        raise VantiaError("user_id is required", code="user_id_required")
    try:
        delta = int(amount)
    except (TypeError, ValueError) as exc:
        raise VantiaError(
            "amount must be a whole number of credits", code="ledger_amount_invalid"
        ) from exc
    if delta == 0:
        raise VantiaError("amount must be non-zero", code="ledger_amount_invalid")
    ledger = default_ledger()
    entry = ledger.apply(
        user_id,
        delta,
        kind="grant" if delta > 0 else "adjustment",
        ref=ref or f"admin:{user_id}:{uuid.uuid4().hex[:16]}",
        meta={"source": "admin", "note": note},
    )
    config = load_credits_config(state_dir)
    tier = tier_of(ledger, user_id)
    return {
        "user_id": user_id,
        "balance": ledger.balance(user_id),
        "tier": tier,
        "monthly_allowance": tier_tokens(tier, config),
        "entry": entry,
        "ts": datetime.now(UTC).isoformat(),
    }


def user_credits(user_id: str, *, state_dir: str | None = None) -> dict[str, Any]:
    """Read-only credit summary for one user (admin view)."""
    if not user_id:
        raise VantiaError("user_id is required", code="user_id_required")
    ledger = default_ledger()
    config = load_credits_config(state_dir)
    tier = tier_of(ledger, user_id)
    return {
        "user_id": user_id,
        "balance": ledger.balance(user_id),
        "tier": tier,
        "monthly_allowance": tier_tokens(tier, config),
        "summary": ledger.summary(user_id),
        "recent_entries": ledger.entries(user_id, limit=20),
        "ts": datetime.now(UTC).isoformat(),
    }
