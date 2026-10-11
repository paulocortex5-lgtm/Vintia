"""Offline credit statements (task 7.3) — deterministic, read-only.

An invoice here is a *credit statement*: a deterministic document derived
from the append-only ledger for one user and one calendar month. The same
ledger + period always produce the same ``invoice_id`` and totals.

Honesty rules:

* The ledger counts **credits, never money** — no USD figure is invented
  for a credit movement (no fabricated FX). Lines carry the signed
  credit amount and the caller-supplied ``ref`` that caused it.
* Generation is gated by the ``invoice_generation`` feature flag; when it
  is off the call raises ``invoice_generation_disabled`` loudly instead
  of silently producing (or silently withholding) a document.
* Read-only: nothing here writes to the ledger or the mirror.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from ..errors import VantiaError
from ..feature_flags import flags as feature_flags
from .ledger import CreditLedger, default_ledger

__all__ = ["generate_invoice"]

_PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _period(month: str | None) -> str:
    if month:
        if not _PERIOD_RE.match(month):
            raise VantiaError(
                f"month must be YYYY-MM, got {month!r}", code="invoice_period_invalid"
            )
        return month
    return datetime.now(UTC).strftime("%Y-%m")


def generate_invoice(
    user_id: str,
    *,
    month: str | None = None,
    ledger: CreditLedger | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One user's credit statement for ``month`` (default: current UTC month).

    Identities: ``invoice_id = "inv_" + sha256(user|period)[:16]`` — stable
    across calls, so a download or an E2E comparison can rely on it.
    """
    if not user_id:
        raise VantiaError("user_id is required", code="user_id_required")
    resolved = _period(month)
    if not feature_flags(environ=environ).get("invoice_generation", False):
        raise VantiaError(
            "invoice generation is disabled (feature flag off)",
            code="invoice_generation_disabled",
        )
    active = ledger if ledger is not None else default_ledger()
    entries = [e for e in active.entries(user_id) if str(e.get("ts", "")).startswith(resolved)]
    earned = sum(int(e["amount"]) for e in entries if int(e["amount"]) > 0)
    spent = -sum(int(e["amount"]) for e in entries if int(e["amount"]) < 0)
    digest = hashlib.sha256(f"{user_id}|{resolved}".encode()).hexdigest()[:16]
    return {
        "invoice_id": f"inv_{digest}",
        "user_id": user_id,
        "period": resolved,
        "unit": "credits",  # the ledger's unit — never an invented currency
        "tier": active.tier_of(user_id),
        "lines": [
            {
                "ts": e.get("ts", ""),
                "ref": e.get("ref", ""),
                "kind": e.get("kind", ""),
                "amount": int(e["amount"]),
                "balance_after": int(e.get("balance_after", 0)),
            }
            for e in entries
        ],
        "total_earned": earned,
        "total_spent": spent,
        "net": earned - spent,
        "balance": active.balance(user_id),
    }
