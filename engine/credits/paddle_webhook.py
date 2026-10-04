"""Paddle webhook handling (task 12.3).

Paddle delivers ``transaction.*`` notifications to
``POST /api/paddle/webhook``. This module implements the verification and
idempotent credit-apply logic; the FastAPI route (Phase 5.3+) wires it up.

Response-time contract (§G.7, R51): the route must answer Paddle within 5
seconds, so this handler does only a bounded amount of work — one
idempotency lookup, one ledger top-up, one event-row upsert.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any

from ..errors import PaddleError

#: Paddle allows at most 5 seconds of clock drift on the signed timestamp.
SIGNATURE_TOLERANCE_SEC = 5.0


def _ts_fresh(ts: str) -> bool:
    """True when the signed timestamp is within the replay window."""
    try:
        return abs(time.time() - int(ts)) <= SIGNATURE_TOLERANCE_SEC
    except ValueError:
        return False


def verify_signature(raw_body: bytes, signature_header: str, secret: str | None = None) -> bool:
    """Verify Paddle's ``Paddle-Signature`` header (``ts=<ts>;h1=<hex>``).

    Paddle signs ``<ts>:<raw_body>`` with HMAC-SHA256 keyed on the
    notification-destination secret (§G.3). A missing/undated/malformed
    signature, or one older than 5 s, is rejected.
    """
    secret = secret if secret is not None else os.environ.get("PADDLE_WEBHOOK_SECRET", "")
    if not secret or not signature_header:
        return False
    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(";") if "=" in p)
        ts = parts["ts"].strip()
        provided = parts["h1"].strip().lower()
    except (KeyError, ValueError):
        return False
    if not _ts_fresh(ts):
        return False
    expected = hmac.new(
        secret.encode(),
        f"{ts}:{raw_body.decode('utf-8', 'replace')}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(provided, expected)


def _default_client() -> Any:
    """The process-wide Supabase client (inject a fake in tests)."""
    from ..persistence import SupabaseClient

    return SupabaseClient()


def _apply_topup(user_id: str, credits: int, event_id: str) -> str:
    """Credit the balance via the ledger (Phase 11). Idempotent by event_id."""
    try:
        from .ledger import topup_from_paddle
    except ImportError:
        return "unavailable"  # Phase 11 not built yet; row already recorded
    try:
        topup_from_paddle(user_id, credits, event_id)
        return "ok"
    except PaddleError:
        return "failed"


def handle_webhook(
    raw_body: bytes,
    signature_header: str,
    *,
    supabase_client: Any | None = None,
) -> dict[str, str]:
    """Process one Paddle webhook delivery (see module docstring for rules).

    Returns a JSON-safe result the route echoes back; a bad signature raises
    :class:`~engine.errors.PaddleError` so the route can answer 400.
    """
    if not verify_signature(raw_body, signature_header):
        raise PaddleError("invalid Paddle-Signature header")
    event = json.loads(raw_body)
    event_id = str(event.get("event_id", ""))
    event_type = str(event.get("event_type", ""))
    occurred_at = str(event.get("occurred_at", ""))
    client = supabase_client if supabase_client is not None else _default_client()

    # R50 — idempotency: Paddle delivers at least once; event_id is the key.
    existing = client.query("paddle_events", {"event_id": event_id}, service=True)
    if existing:
        return {"status": "already_processed", "event_id": event_id}

    custom = event.get("custom_data") or {}
    user_id = str(custom.get("user_id", ""))
    try:
        credits = int(custom.get("credits", 0))
    except (TypeError, ValueError):
        credits = 0

    status = "recorded"
    ledger_state = "not_required"
    if event_type == "transaction.completed" and user_id and credits > 0:
        ledger_state = _apply_topup(user_id, credits, event_id)
        status = "credited" if ledger_state == "ok" else "ledger_pending"

    client.upsert(
        "paddle_events",
        [
            {
                "event_id": event_id,
                "event_type": event_type,
                "occurred_at": occurred_at,
                "user_id": user_id,
                "credits": credits,
                "status": status,
                "ledger_state": ledger_state,
                "data": event,
                "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ],
        service=True,
    )
    return {"status": status, "event_id": event_id, "ledger": ledger_state}


__all__ = ["SIGNATURE_TOLERANCE_SEC", "handle_webhook", "verify_signature"]
