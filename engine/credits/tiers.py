"""Tier definitions + enforcement (task 11.3).

Tiers are the *monthly token allowance* product model from the state's
``credits`` block — free / pro / business (10k / 100k / 1M by default).
Nothing here hardcodes those numbers: :func:`tier_tokens` reads the same
config the rest of the credits package uses.

Honesty rules:

* A user's tier is **recorded, never inferred** — ``CreditLedger.tier_of``
  defaults to ``free``; upgrading requires an explicit :func:`set_tier`
  (Phase 8's profile/auth layer will call it from verified data).
* The allowance is granted **at most once per calendar month per user**,
  idempotent by the ref ``allowance:<user>:<YYYY-MM>`` — a replay, a race,
  or a second request in the same month moves no credits.
* Enforcement is R46: :func:`enforce` refuses when the balance cannot cover
  the required credits and writes nothing. There is no overdraft.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..errors import InsufficientCredits, VantiaError
from .config import load_credits_config
from .ledger import CreditLedger, default_ledger

__all__ = [
    "TIERS",
    "enforce",
    "ensure_allowance",
    "projected_balance",
    "set_tier",
    "tier_of",
    "tier_tokens",
]

#: The three tiers (state key suffixes: ``<tier>_tier_tokens``).
TIERS = ("free", "pro", "business")

_TIER_KEYS = {
    "free": "free_tier_tokens",
    "pro": "pro_tier_tokens",
    "business": "business_tier_tokens",
}

#: Documented fallback if state carries no credits block (packaged seed values).
FALLBACK_TIER_TOKENS = {"free": 10_000, "pro": 100_000, "business": 1_000_000}


def _validate_tier(tier: str) -> str:
    if tier not in TIERS:
        raise VantiaError(f"unknown tier {tier!r}; known: {', '.join(TIERS)}", code="unknown_tier")
    return tier


def tier_tokens(tier: str, config: dict[str, Any] | None = None) -> int:
    """Monthly token allowance for ``tier`` (state ``credits`` block)."""
    _validate_tier(tier)
    cfg = config if config is not None else load_credits_config()
    value = cfg.get(_TIER_KEYS[tier])
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return FALLBACK_TIER_TOKENS[tier]


def tier_of(ledger: CreditLedger, user_id: str) -> str:
    """Recorded tier for ``user_id`` — ``"free"`` unless explicitly set."""
    return _validate_tier(ledger.tier_of(user_id))


def set_tier(ledger: CreditLedger, user_id: str, tier: str) -> str:
    """Record ``tier`` for ``user_id`` (validated; never inferred)."""
    return ledger.set_tier(user_id, _validate_tier(tier))


def _month(month: str | None) -> str:
    if month:
        return month
    return datetime.now(UTC).strftime("%Y-%m")


def ensure_allowance(
    ledger: CreditLedger | None = None,
    user_id: str = "",
    *,
    tier: str | None = None,
    month: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Grant this month's tier allowance exactly once for ``user_id``.

    Idempotent by ref: calling it again in the same month (any code path —
    API read, pipeline pre-flight, webhook replay) returns the original
    entry and moves no credits. Returns ``{granted, tier, month, amount,
    entry}``.
    """
    active = ledger if ledger is not None else default_ledger()
    if not user_id:
        raise VantiaError("user_id is required", code="user_id_required")
    resolved_tier = _validate_tier(tier) if tier else tier_of(active, user_id)
    period = _month(month)
    ref = f"allowance:{user_id}:{period}"
    existing = active.find_ref(user_id, ref)
    if existing is not None:
        return {
            "granted": False,
            "tier": resolved_tier,
            "month": period,
            "amount": int(existing["amount"]),
            "entry": existing,
        }
    entry = active.grant(
        user_id,
        tier_tokens(resolved_tier, config),
        ref,
        meta={"source": "allowance", "tier": resolved_tier, "month": period},
    )
    return {
        "granted": True,
        "tier": resolved_tier,
        "month": period,
        "amount": int(entry["amount"]),
        "entry": entry,
    }


def projected_balance(
    ledger: CreditLedger | None = None,
    user_id: str = "",
    *,
    month: str | None = None,
    config: dict[str, Any] | None = None,
) -> int:
    """Balance *including* an unclaimed this-month allowance — writes nothing.

    Used by the estimate endpoint so a fresh user sees what they would
    actually have after the idempotent grant runs, without the read
    creating the grant.
    """
    active = ledger if ledger is not None else default_ledger()
    balance = active.balance(user_id)
    period = _month(month)
    if active.find_ref(user_id, f"allowance:{user_id}:{period}") is None:
        balance += tier_tokens(tier_of(active, user_id), config)
    return balance


def enforce(
    ledger: CreditLedger | None = None,
    user_id: str = "",
    *,
    required: int = 0,
) -> int:
    """R46: return the balance when it covers ``required``, else raise.

    Writes nothing — refusal happens before any work is charged.
    """
    active = ledger if ledger is not None else default_ledger()
    balance = active.balance(user_id)
    need = int(required)
    if need < 0:
        raise VantiaError("required credits must be >= 0", code="credits_required_invalid")
    if balance < need:
        raise InsufficientCredits(balance, need)
    return balance
