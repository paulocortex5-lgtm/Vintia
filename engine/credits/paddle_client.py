"""Paddle checkout-transaction creation (task 12.2).

The frontend's ``/credits/purchase`` page calls the backend checkout route,
which in turn invokes :func:`create_checkout_transaction`. Paddle is the
Merchant of Record — Vantia never touches card data (R57). The SDK import is
deferred so that ``import engine`` stays light even when the ``payments``
extra is not installed (§0.7 graceful degradation).
"""

from __future__ import annotations

import os

from ..errors import PaddleError

#: One-time credit packs (business model §A.3).  price -> credits.
CREDIT_PACKS: dict[str, int] = {
    "pack_10k": 10_000,
    "pack_50k": 50_000,
    "pack_250k": 250_000,
}


def _price_env(pack_id: str) -> str:
    """Environment variable that holds the Paddle price id for ``pack_id``."""
    return f"PADDLE_PRICE_{pack_id.upper()}"


def create_checkout_transaction(user_id: str, pack_id: str) -> str:
    """Create a Paddle automatic-purchase transaction and return its checkout URL.

    The price id is read from the environment (see Part G.5); it is never
    hardcoded (R60). ``custom_data`` carries ``{user_id, pack_id, credits}``
    through the transaction so the webhook can attribute the top-up without
    any lookup.

    Return/success URLs are **not** passed per transaction: the pinned
    ``paddle-python-sdk`` surface (``CreateTransaction``) has no such
    fields — they are configured once in Paddle Dashboard → Settings →
    Checkout (verified against the installed SDK in task 12.2 rather than
    accepting dead parameters).

    Raises :class:`~engine.errors.PaddleError` on any SDK/config failure.
    """
    if pack_id not in CREDIT_PACKS:
        raise PaddleError(f"unknown credit pack {pack_id!r}; known: {sorted(CREDIT_PACKS)}")
    price_id = os.environ.get(_price_env(pack_id), "")
    if not price_id:
        raise PaddleError(f"price id for {pack_id!r} not configured ({_price_env(pack_id)} unset)")
    api_key = os.environ.get("PADDLE_API_KEY", "")
    if not api_key:
        raise PaddleError("PADDLE_API_KEY is not set")

    # Deferred import: the SDK is an optional extra.
    try:
        from paddle_billing import Client, Environment
        from paddle_billing.Resources.Transactions.Operations import CreateTransaction
    except ImportError as exc:  # pragma: no cover - SDK not installed
        raise PaddleError(f"paddle-python-sdk not installed: {exc}") from exc

    environment = (
        Environment.PRODUCTION
        if (os.environ.get("PADDLE_ENVIRONMENT", "sandbox") == "production")
        else Environment.SANDBOX
    )
    client = Client(api_key, environment=environment)

    transaction = client.transactions.create(
        CreateTransaction(
            items=[{"price_id": price_id, "quantity": 1}],
            custom_data={
                "user_id": user_id,
                "pack_id": pack_id,
                "credits": str(CREDIT_PACKS[pack_id]),
            },
        )
    )
    return transaction.checkout.url


__all__ = ["CREDIT_PACKS", "create_checkout_transaction"]
