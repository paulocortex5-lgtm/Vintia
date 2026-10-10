"""Waitlist with double opt-in (task 5.6).

Honest offline design:

* **Double opt-in is real** — ``subscribe`` stores ``pending`` and only
  ``confirm(token)`` flips the row to ``confirmed``. Nothing is ever
  pre-checked, and the API response never contains the token.
* **Tokens are stored hashed** — only ``sha256(token)`` is persisted, so a
  database leak cannot confirm anybody. Re-subscribing rotates the token,
  invalidating any earlier link.
* **Delivery without a provider** — the default sender is
  :class:`OutboxSender`, which writes the confirmation message to
  ``.vantia/outbox/`` (the same pattern the incident reporter uses for
  offline drafts): the email isn't faked or silently dropped; it lands in
  a reviewable outbox until a real provider is configured at launch.
* **Loud backend** — an unconfigured Supabase raises
  ``waitlist_backend_unconfigured``; an empty list is never returned as
  "nobody signed up".
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from typing import Any

from .errors import VantiaError
from .json_utils import atomic_write_json
from .logging_config import utc_now

__all__ = ["OutboxSender", "WaitlistService", "normalize_email"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    """Lowercase + strip an email, refusing anything implausible."""
    cleaned = (email or "").strip().lower()
    if not _EMAIL_RE.match(cleaned) or len(cleaned) > 254:
        raise VantiaError(f"invalid email: {email!r}", code="invalid_email")
    return cleaned


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class OutboxSender:
    """Writes confirmation messages to ``.vantia/outbox/`` (launch: swap
    for a real provider by injecting any object with ``send_confirmation``)."""

    def __init__(self, outbox_dir: str | None = None) -> None:
        self.outbox_dir = outbox_dir or os.environ.get(
            "VANTIA_OUTBOX_DIR", os.path.join(".vantia", "outbox")
        )

    def send_confirmation(self, email: str, token: str) -> str:
        """Queue one confirmation message; returns the outbox file path."""
        stamp = utc_now().replace(":", "").replace("-", "")
        digest = hashlib.sha256(f"{email}|{token}".encode()).hexdigest()[:16]
        path = os.path.join(self.outbox_dir, f"{stamp}-{digest}.json")
        atomic_write_json(
            path,
            {
                "to": email,
                "subject": "Confirm your Vantia waitlist signup",
                "token": token,
                "body": (
                    "Confirm your waitlist signup by POSTing this token to "
                    f"/waitlist/confirm (link: /waitlist/confirm?token={token}). "
                    "You are not on the list until it is confirmed."
                ),
                "queued_at": utc_now(),
                "delivery": "outbox — no email provider configured yet",
            },
        )
        return path


class WaitlistService:
    """Subscribe / confirm / stats over the ``waitlist`` table (0006)."""

    def __init__(self, supabase_client: Any | None = None, sender: Any | None = None) -> None:
        from .persistence import SupabaseClient

        self.client = supabase_client if supabase_client is not None else SupabaseClient()
        self.sender = sender if sender is not None else OutboxSender()

    def _require_backend(self) -> None:
        if not getattr(self.client, "configured", False):
            raise VantiaError(
                "Supabase is not configured; the waitlist needs a real backend",
                code="waitlist_backend_unconfigured",
            )

    @staticmethod
    def _public(row: dict[str, Any]) -> dict[str, Any]:
        """Response shape — never leaks ``token_hash``."""
        return {"email": row.get("email", ""), "status": row.get("status", "pending")}

    def subscribe(self, email: str) -> dict[str, Any]:
        """Start (or restart) the double opt-in for ``email``."""
        self._require_backend()
        normalized = normalize_email(email)
        existing = self.client.query("waitlist", {"email": f"eq.{normalized}"}, service=True)
        if existing and existing[0].get("status") == "confirmed":
            return {**self._public(existing[0]), "confirmation_sent": False}
        token = secrets.token_urlsafe(32)
        row = {
            "email": normalized,
            "status": "pending",
            "token_hash": _hash_token(token),
            "created_at": utc_now(),
            "confirmed_at": "",
        }
        self.client.upsert("waitlist", [row], service=True)
        self.sender.send_confirmation(normalized, token)
        return {"email": normalized, "status": "pending", "confirmation_sent": True}

    def confirm(self, token: str) -> dict[str, Any]:
        """Redeem a confirmation token; idempotent for an already-on list."""
        self._require_backend()
        if not token:
            raise VantiaError("confirmation token is required", code="waitlist_token_required")
        rows = self.client.query(
            "waitlist", {"token_hash": f"eq.{_hash_token(token)}"}, service=True
        )
        if not rows:
            raise VantiaError(
                "confirmation token is invalid or expired", code="waitlist_token_invalid"
            )
        row = rows[0]
        if row.get("status") == "confirmed":
            return {**self._public(row), "already": True}
        confirmed = {**row, "status": "confirmed", "confirmed_at": utc_now()}
        self.client.upsert("waitlist", [confirmed], service=True)
        return {**self._public(confirmed), "already": False}

    def stats(self) -> dict[str, int]:
        """Confirmed/pending counts (pre-launch scale: filtered reads)."""
        self._require_backend()
        confirmed = self.client.query("waitlist", {"status": "eq.confirmed"}, service=True)
        pending = self.client.query("waitlist", {"status": "eq.pending"}, service=True)
        return {"confirmed_count": len(confirmed), "pending_count": len(pending)}
