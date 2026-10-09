"""Credit system (Phases 11 + 12) — ledger, metering, tiers, Paddle.

Vantia uses Paddle as its Merchant of Record: the frontend opens Paddle
Checkout, and :mod:`engine.credits.paddle_webhook` applies the credit top-up
once Paddle confirms the transaction. Stripe was fully removed in v6.0
(§B, R56–R60).

The credit *system* itself (task 11.x) sits underneath: a local-first
append-only :class:`CreditLedger` (11.1), token-price metering middleware
(11.2), free/pro/business tier allowances with R46 enforcement (11.3), and
charge-on-completion wiring in the pipelines (11.4).
"""

from __future__ import annotations

from ..errors import InsufficientCredits, PaddleError
from .config import load_credits_config
from .ledger import CreditLedger, default_ledger, reset_default_ledger, topup_from_paddle
from .metering import CreditMeter, default_meter, operation_cost, reset_default_meter
from .paddle_client import CREDIT_PACKS, create_checkout_transaction
from .paddle_webhook import handle_webhook, verify_signature
from .tiers import (
    TIERS,
    enforce,
    ensure_allowance,
    projected_balance,
    set_tier,
    tier_of,
    tier_tokens,
)

__all__ = [
    "CREDIT_PACKS",
    "TIERS",
    "CreditLedger",
    "CreditMeter",
    "InsufficientCredits",
    "PaddleError",
    "create_checkout_transaction",
    "default_ledger",
    "default_meter",
    "enforce",
    "ensure_allowance",
    "handle_webhook",
    "load_credits_config",
    "operation_cost",
    "projected_balance",
    "reset_default_ledger",
    "reset_default_meter",
    "set_tier",
    "tier_of",
    "tier_tokens",
    "topup_from_paddle",
    "verify_signature",
]
