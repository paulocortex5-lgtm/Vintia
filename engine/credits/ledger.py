"""Credit ledger + balance tables (task 11.1).

Append-only, per-user credit ledger — the missing dependency named in
PLATFORM_STATE §11 that kept Paddle top-ups stuck at ``ledger_pending``.

Design (repo rules carried over):

* **Local-first / git-authoritative** — the ledger file
  (``$VANTIA_CREDITS_DIR/ledger.json``, default ``.vantia/credits/``) is the
  source of truth, mirroring every other ``.vantia/`` store; Supabase
  ``credit_ledger`` / ``credit_balances`` are a best-effort write-through that
  never raises (STEP K).
* **Append-only audit trail** — every movement is one entry with a signed
  ``amount``, the ``balance_after`` it produced and a caller-supplied ``ref``.
  Nothing is ever edited or deleted; a balance is just the sum of entries.
* **Idempotent by ``ref``** — replaying the same ref (Paddle webhook
  redelivery, a retried charge) returns the original entry and moves no
  money. ``topup_from_paddle`` therefore credits exactly once per event.
* **Never invent** — a spend that would go below zero raises
  :class:`~engine.errors.InsufficientCredits` (R46) and writes nothing;
  there is no overdraft, no negative balance, no silent clamp.
* **Thread-safe** — one re-entrant lock around load-modify-save; writes go
  through ``atomic_write_json``.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from ..errors import InsufficientCredits, PaddleError, VantiaError
from ..json_utils import atomic_write_json, load_json
from ..logging_config import utc_now

LOGGER = logging.getLogger("vantia.credits.ledger")

DEFAULT_CREDITS_DIR = ".vantia/credits"
LEDGER_FILENAME = "ledger.json"
LEDGER_VERSION = 1
ENTRY_KINDS = ("topup", "grant", "spend", "refund", "adjustment")


def _store_path(store_path: str | None = None) -> str:
    if store_path:
        return store_path
    base = os.environ.get("VANTIA_CREDITS_DIR", DEFAULT_CREDITS_DIR)
    return os.path.join(base, LEDGER_FILENAME)


class CreditLedger:
    """Thread-safe credit ledger with an optional Supabase mirror."""

    def __init__(
        self, store_path: str | None = None, *, supabase_client: Any | None = None
    ) -> None:
        self.path = _store_path(store_path)
        self.supabase = supabase_client
        self._lock = threading.RLock()

    # ── Persistence ─────────────────────────────────────────────────
    def _load(self) -> dict[str, Any]:
        try:
            data = load_json(self.path)
        except ValueError as exc:  # json.JSONDecodeError — never reset money
            raise VantiaError(
                f"credit ledger at {self.path} is corrupt; refusing to reset balances",
                code="ledger_corrupt",
            ) from exc
        if data is None:  # absent file → a fresh, empty ledger
            data = {"version": LEDGER_VERSION, "users": {}, "tiers": {}}
        if not isinstance(data, dict):  # hand-edited garbage → loud, not a wipe
            raise VantiaError(
                f"credit ledger at {self.path} is corrupt; refusing to reset balances",
                code="ledger_corrupt",
            )
        if not isinstance(data.get("users"), dict):
            data["users"] = {}
        if not isinstance(data.get("tiers"), dict):
            data["tiers"] = {}
        data.setdefault("version", LEDGER_VERSION)
        return data

    def _save(self, data: dict[str, Any]) -> None:
        data["updated_at"] = utc_now()
        atomic_write_json(self.path, data)

    # ── Core movements (signed amounts) ─────────────────────────────
    def apply(
        self,
        user_id: str,
        amount: int,
        *,
        kind: str,
        ref: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply one signed ``amount``; idempotent by ``(user_id, ref)``.

        Returns the stored entry — when ``ref`` was already applied this is
        the *original* entry and no money moves. Raises
        :class:`~engine.errors.VantiaError` codes for invalid input and
        :class:`~engine.errors.InsufficientCredits` (R46) when the result
        would drop below zero (nothing is written in that case).
        """
        if not user_id:
            raise VantiaError("user_id is required", code="user_id_required")
        if kind not in ENTRY_KINDS:
            raise VantiaError(
                f"invalid ledger kind {kind!r}; known: {', '.join(ENTRY_KINDS)}",
                code="ledger_kind_invalid",
            )
        if not ref:
            raise VantiaError("ledger ref is required for idempotency", code="ledger_ref_required")
        delta = int(amount)
        if delta == 0:
            raise VantiaError("ledger amount must be non-zero", code="ledger_amount_invalid")

        with self._lock:
            data = self._load()
            user = data["users"].setdefault(user_id, {"balance": 0, "entries": []})
            user.setdefault("entries", [])
            for existing in user["entries"]:
                if existing.get("ref") == ref:
                    return dict(existing)  # replay: no money moves
            balance = int(user.get("balance", 0))
            new_balance = balance + delta
            if new_balance < 0:
                raise InsufficientCredits(balance, -delta)
            entry: dict[str, Any] = {
                "ts": utc_now(),
                "kind": kind,
                "amount": delta,
                "balance_after": new_balance,
                "ref": ref,
                "meta": dict(meta or {}),
            }
            user["balance"] = new_balance
            user["entries"].append(entry)
            self._save(data)
        self._mirror(user_id, entry, new_balance)
        return dict(entry)

    # ── Semantic wrappers ───────────────────────────────────────────
    def topup(
        self,
        user_id: str,
        amount: int,
        ref: str,
        *,
        kind: str = "topup",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Credit ``amount`` (> 0). ``kind`` distinguishes packs from grants."""
        if int(amount) <= 0:
            raise VantiaError("topup amount must be positive", code="ledger_amount_invalid")
        return self.apply(user_id, int(amount), kind=kind, ref=ref, meta=meta)

    def grant(
        self, user_id: str, amount: int, ref: str, *, meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Credit a tier allowance / bonus (``amount`` > 0)."""
        return self.topup(user_id, amount, ref, kind="grant", meta=meta)

    def spend(
        self, user_id: str, amount: int, ref: str, *, meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Debit ``amount`` (> 0); R46 :class:`InsufficientCredits` when short."""
        if int(amount) <= 0:
            raise VantiaError("spend amount must be positive", code="ledger_amount_invalid")
        return self.apply(user_id, -int(amount), kind="spend", ref=ref, meta=meta)

    def refund(
        self, user_id: str, amount: int, ref: str, *, meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Return previously spent credits (``amount`` > 0)."""
        if int(amount) <= 0:
            raise VantiaError("refund amount must be positive", code="ledger_amount_invalid")
        return self.apply(user_id, int(amount), kind="refund", ref=ref, meta=meta)

    # ── Reads ───────────────────────────────────────────────────────
    def balance(self, user_id: str) -> int:
        """Current balance (0 for an unknown user — never a fabricated credit)."""
        with self._lock:
            data = self._load()
            user = data["users"].get(user_id) or {}
            return int(user.get("balance", 0))

    def entries(self, user_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Chronological entry list, optionally truncated to the newest ``limit``."""
        with self._lock:
            data = self._load()
            user = data["users"].get(user_id) or {}
            rows = [dict(e) for e in user.get("entries", [])]
        if limit is not None and limit >= 0:
            rows = rows[-limit:] if limit else []
        return rows

    def find_ref(self, user_id: str, ref: str) -> dict[str, Any] | None:
        """Return the entry for ``ref`` if it was already applied, else ``None``."""
        with self._lock:
            data = self._load()
            user = data["users"].get(user_id) or {}
            for entry in user.get("entries", []):
                if entry.get("ref") == ref:
                    return dict(entry)
        return None

    def summary(self, user_id: str) -> dict[str, Any]:
        """Aggregate balance data for the credits dashboard (task 11.5)."""
        rows = self.entries(user_id)
        earned = sum(e["amount"] for e in rows if e["amount"] > 0)
        spent = -sum(e["amount"] for e in rows if e["amount"] < 0)
        return {
            "balance": self.balance(user_id),
            "entry_count": len(rows),
            "total_earned": earned,
            "total_spent": spent,
            "last_entry_ts": rows[-1]["ts"] if rows else None,
        }

    # ── Tier mapping (definitions + enforcement live in tiers.py) ───
    def tier_of(self, user_id: str) -> str:
        """The user's tier; ``"free"`` by default (never a guessed upgrade)."""
        with self._lock:
            data = self._load()
            return str(data["tiers"].get(user_id) or "free")

    def set_tier(self, user_id: str, tier: str) -> str:
        """Record ``tier`` for the user (validated by tiers.py callers)."""
        with self._lock:
            data = self._load()
            data["tiers"][user_id] = tier
            self._save(data)
        return tier

    # ── Supabase mirror (best-effort, never raises) ─────────────────
    def _mirror(self, user_id: str, entry: dict[str, Any], balance: int) -> None:
        client = self.supabase
        if not client:
            return
        try:
            client.upsert("credit_ledger", [{**entry, "user_id": user_id}], service=True)
            client.upsert(
                "credit_balances",
                [{"user_id": user_id, "balance": balance, "updated_at": entry["ts"]}],
                service=True,
            )
        except Exception:  # noqa: BLE001 — mirroring must never break a movement
            LOGGER.warning("credit mirror failed; local ledger is authoritative")


_default_ledger: CreditLedger | None = None


def default_ledger() -> CreditLedger:
    """Process-wide ledger ($VANTIA_CREDITS_DIR/.vantia/credits/ledger.json)."""
    global _default_ledger
    if _default_ledger is None:
        _default_ledger = CreditLedger()
    return _default_ledger


def reset_default_ledger() -> None:
    """Test hook: drop the singleton (paths change via ``VANTIA_CREDITS_DIR``)."""
    global _default_ledger
    _default_ledger = None


def topup_from_paddle(
    user_id: str, credits: int, event_id: str, *, ledger: CreditLedger | None = None
) -> dict[str, Any]:
    """Credit a Paddle top-up, idempotent by ``event_id`` (webhook contract).

    Storage failures surface as :class:`~engine.errors.PaddleError` so
    :func:`engine.credits.paddle_webhook.handle_webhook` records the event as
    ``ledger_pending`` instead of crashing the 5-second response window.
    """
    active = ledger if ledger is not None else default_ledger()
    try:
        return active.topup(
            user_id,
            int(credits),
            ref=f"paddle:{event_id}",
            meta={"source": "paddle", "event_id": event_id},
        )
    except OSError as exc:
        raise PaddleError(f"credit ledger unavailable: {exc}") from exc


__all__ = [
    "DEFAULT_CREDITS_DIR",
    "ENTRY_KINDS",
    "CreditLedger",
    "default_ledger",
    "reset_default_ledger",
    "topup_from_paddle",
]
