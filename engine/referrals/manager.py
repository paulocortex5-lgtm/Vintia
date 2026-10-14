"""Referral program (task 15.11).

A user gets a stable 8-char code; when a new user signs up through it,
**both** parties are credited 5,000 tokens exactly once (idempotent — a
referee can never credit twice, R no-double-credit).

Design (repo rules carried over):

* **Local-first / git-authoritative** — ``.vantia/referrals/referrals.json``
  holds the code→user map and the referral rows; a Supabase mirror is
  best-effort, never raising.
* **Idempotent crediting** — the credit ref is ``referral:<code>:<referee_id>``
  so :meth:`CreditLedger.find_ref` short-circuits any replay; a second
  signup with the same referee moves no credits.
* **Codes are unique** — ``generate_code`` retries on collision so two
  users never share a code.
* **Owner isolation (R26)** — history reads are scoped to the referrer.
"""

from __future__ import annotations

import logging
import os
import secrets
import string
import threading
from typing import Any

from ..credits import default_ledger
from ..errors import VantiaError
from ..json_utils import atomic_write_json, load_json
from ..logging_config import utc_now

__all__ = [
    "REFERRAL_BONUS",
    "code_for",
    "generate_code",
    "history_for",
    "record_signup",
    "referrer_for_code",
]

LOGGER = logging.getLogger("vantia.referrals.manager")

STORE_VERSION = 1

#: §15.5 — credit granted to each party on a successful referral.
REFERRAL_BONUS = 5000

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8

_store_lock = threading.RLock()


def _default_dir() -> str:
    return os.environ.get("VANTIA_REFERRALS_DIR", os.path.join(".vantia", "referrals"))


def _store_file() -> str:
    return os.path.join(_default_dir(), "referrals.json")


def _load_all() -> dict[str, Any]:
    data = load_json(_store_file())
    if not isinstance(data, dict) or not isinstance(data.get("codes"), dict):
        return {"version": STORE_VERSION, "codes": {}, "referrals": []}
    return data


def _save_all(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_store_file()), exist_ok=True)
    atomic_write_json(_store_file(), data)


def _new_code(existing: set[str]) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        if code not in existing:
            return code
    raise VantiaError(
        "could not allocate a unique referral code", code="code_exhausted"
    )  # pragma: no cover


def generate_code(user_id: str) -> str:
    """Return the user's referral code, creating a unique one if absent.

    Stable: a user who already has a code gets the same one back.
    """
    if not user_id:
        raise VantiaError("user_id is required", code="user_id_required")
    with _store_lock:
        data = _load_all()
        existing = data["codes"].get(user_id)
        if existing:
            return str(existing["code"])
        code = _new_code({c["code"] for c in data["codes"].values()})
        data["codes"][user_id] = {"code": code, "created_at": utc_now()}
        _save_all(data)
    return code


def code_for(user_id: str) -> str:
    """The user's code, generating one on first request (idempotent)."""
    return generate_code(user_id)


def referrer_for_code(code: str) -> str | None:
    """Resolve a referral code to its owning user_id, or None."""
    if not code:
        return None
    code = code.strip().upper()
    for user_id, entry in _load_all()["codes"].items():
        if str(entry.get("code", "")).upper() == code:
            return user_id
    return None


def history_for(referrer_id: str) -> list[dict[str, Any]]:
    """All referral rows for one referrer, newest first (R26 isolation)."""
    rows = [r for r in _load_all()["referrals"] if r.get("referrer_id") == referrer_id]
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows


def record_signup(
    code: str,
    referee_id: str,
    referee_email: str = "",
    *,
    ledger: Any | None = None,
) -> dict[str, Any]:
    """Credit both parties 5,000 on a referral signup (task 15.11 §15.2).

    Idempotent by ``(code, referee_id)``: the same referee crediting twice
    returns the original row and moves no credits. A self-referral (the
    referrer signing up through their own code) is refused.
    """
    if not code or not referee_id:
        raise VantiaError("code and referee_id are required", code="referral_fields_required")
    referrer = referrer_for_code(code)
    if referrer is None:
        raise VantiaError(f"unknown referral code {code!r}", code="referral_code_invalid")
    if referrer == referee_id:
        raise VantiaError("self-referral is not creditable", code="self_referral")

    active = ledger or default_ledger()
    ref = f"referral:{code.upper()}:{referee_id}"

    with _store_lock:
        data = _load_all()
        for row in data["referrals"]:
            if row.get("code", "").upper() == code.upper() and row.get("referee_id") == referee_id:
                return {**row, "credited": False}
        row = {
            "code": code.upper(),
            "referrer_id": referrer,
            "referee_email": referee_email,
            "referee_id": referee_id,
            "status": "completed",
            "amount": REFERRAL_BONUS,
            "created_at": utc_now(),
        }
        data["referrals"].append(row)
        _save_all(data)

    # Idempotent credits (find_ref short-circuits a replay).
    active.grant(
        referee_id,
        REFERRAL_BONUS,
        ref=ref,
        meta={"source": "referral", "role": "referee", "code": code.upper()},
    )
    active.grant(
        referrer,
        REFERRAL_BONUS,
        ref=f"{ref}:referrer",
        meta={"source": "referral", "role": "referrer", "code": code.upper()},
    )
    row["credited_at"] = utc_now()
    return {**row, "credited": True}
