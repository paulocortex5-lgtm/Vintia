"""Token metering middleware (task 11.2).

Prices product operations in **credits (= tokens)** from the state's
``credits.token_costs`` table (``cv_scan`` 2000, ``cv_improvement`` 8000,
``cover_letter`` 5000, …) and meters their deduction through the ledger.

The middleware contract (used by the pipelines in task 11.4):

1. **Pre-flight** — :meth:`CreditMeter.preflight` grants the current month's
   tier allowance (idempotent) and then enforces R46 *before any work*
   starts: an underfunded run is refused with ``insufficient_credits`` and
   nothing is fetched, parsed or written.
2. **Charge on completion** — :meth:`CreditMeter.charge` runs only after the
   caller succeeded, idempotent by ``ref``; a failed run costs nothing.
   :meth:`CreditMeter.metered` packages both halves as a context manager.

Pricing is deliberately fixed per operation from config: no exchange rate
between USD spend and tokens exists anywhere in the spec, so this module
never guesses one. Actual LLM token usage is recorded by the existing cost
ledger (``engine/cost_tracker``) and quota tracker; a deployment re-prices
by editing ``state.json`` — not by hardcoding here.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from ..errors import VantiaError
from .config import load_credits_config
from .ledger import CreditLedger, default_ledger
from .tiers import enforce, ensure_allowance, projected_balance, tier_of, tier_tokens

__all__ = ["CreditMeter", "default_meter", "operation_cost", "reset_default_meter"]


def operation_cost(operation: str, config: dict[str, Any] | None = None) -> int:
    """Credit (token) price of one ``operation`` from state ``token_costs``.

    Raises ``VantiaError(code="unknown_operation")`` listing the known
    operations — an unpriced operation is never run for free by accident.
    """
    cfg = config if config is not None else load_credits_config()
    costs = cfg.get("token_costs")
    if not isinstance(costs, dict) or operation not in costs:
        known = sorted(costs) if isinstance(costs, dict) else []
        raise VantiaError(
            f"operation {operation!r} is not priced; known: {', '.join(known) or '(none)'}",
            code="unknown_operation",
            operation=operation,
            known=known,
        )
    try:
        cost = int(costs[operation])
    except (TypeError, ValueError) as exc:
        raise VantiaError(
            f"operation {operation!r} has a non-integer price", code="operation_price_invalid"
        ) from exc
    if cost < 0:
        raise VantiaError(
            f"operation {operation!r} has a negative price", code="operation_price_invalid"
        )
    return cost


class CreditMeter:
    """Pre-flight + charge-on-completion metering over a :class:`CreditLedger`."""

    def __init__(
        self,
        ledger: CreditLedger | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.ledger = ledger if ledger is not None else default_ledger()
        self.config = config  # None → read state.json on demand (test-injectable)

    # ── Pricing / estimates ─────────────────────────────────────────
    def cost(self, operation: str) -> int:
        return operation_cost(operation, self.config)

    def estimate(self, user_id: str, operation: str) -> dict[str, Any]:
        """Affordability report for one operation (UI + pre-flight display).

        ``available`` counts an unclaimed this-month allowance without
        granting it; ``balance`` is the literal ledger balance.
        """
        cost = self.cost(operation)
        balance = self.ledger.balance(user_id)
        available = projected_balance(self.ledger, user_id, config=self.config)
        shortfall = max(0, cost - available)
        return {
            "user_id": user_id,
            "operation": operation,
            "cost": cost,
            "balance": balance,
            "available": available,
            "affordable": shortfall == 0,
            "shortfall": shortfall,
        }

    # ── Middleware halves ───────────────────────────────────────────
    def preflight(self, user_id: str, operation: str) -> dict[str, Any]:
        """Allowance grant + R46 enforcement *before* work starts."""
        ensure_allowance(self.ledger, user_id, config=self.config)
        cost = self.cost(operation)
        balance = enforce(self.ledger, user_id, required=cost)
        tier = tier_of(self.ledger, user_id)
        return {
            "user_id": user_id,
            "operation": operation,
            "cost": cost,
            "balance_after_allowance": balance,
            "tier": tier,
            "monthly_allowance": tier_tokens(tier, self.config),
        }

    def charge(
        self,
        user_id: str,
        operation: str,
        ref: str,
        *,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Deduct ``operation``'s price on completion; idempotent by ``ref``."""
        cost = self.cost(operation)
        entry = self.ledger.spend(
            user_id,
            cost,
            ref,
            meta={"source": "meter", "operation": operation, **(meta or {})},
        )
        return {
            "user_id": user_id,
            "operation": operation,
            "cost": cost,
            "ref": ref,
            "balance_after": entry["balance_after"],
            "entry": entry,
        }

    @contextmanager
    def metered(
        self, user_id: str, operation: str, ref: str, *, meta: dict[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        """Pre-flight on enter, charge on clean exit; exceptions cost nothing."""
        plan = self.preflight(user_id, operation)
        yield plan
        self.charge(user_id, operation, ref, meta=meta)


_default_meter: CreditMeter | None = None


def default_meter() -> CreditMeter:
    """Process-wide meter (default ledger + state config)."""
    global _default_meter
    if _default_meter is None:
        _default_meter = CreditMeter()
    return _default_meter


def reset_default_meter() -> None:
    """Test hook: drop the singleton (pairs with ``reset_default_ledger``)."""
    global _default_meter
    _default_meter = None
