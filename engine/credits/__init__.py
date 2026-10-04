"""Credit purchasing (Phase 12) — Paddle Billing integration.

Vantia uses Paddle as its Merchant of Record: the frontend opens Paddle
Checkout, and :mod:`engine.credits.paddle_webhook` applies the credit top-up
once Paddle confirms the transaction. Stripe was fully removed in v6.0
(§B, R56–R60).
"""

from __future__ import annotations

from ..errors import PaddleError
from .paddle_client import CREDIT_PACKS, create_checkout_transaction
from .paddle_webhook import handle_webhook, verify_signature

__all__ = [
    "CREDIT_PACKS",
    "PaddleError",
    "create_checkout_transaction",
    "handle_webhook",
    "verify_signature",
]
