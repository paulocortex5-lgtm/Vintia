"""Public API for universities (task 15.12).

Institutions get a ``vantia_sk_...`` key to score CVs and look up
credential equivalence programmatically. Keys are stored **hashed**
(SHA-256) — the raw key is shown once at creation and never persisted.

Design (repo rules carried over):

* **Hash-only storage** — :func:`hash_key` is the only form stored; the
  raw key exists only in the creation response.
* **Per-key rate limiting** — an in-memory sliding window (10/min free,
  100/min business) with the ``X-RateLimit-*`` headers; the limiter is
  process-local and best-effort (a cold Render instance resets it), which
  is acceptable for the documented limits.
* **Local-first / git-authoritative** — ``.vantia/api_keys/api_keys.json``
  is the source of truth; a Supabase mirror is best-effort.
* **Tier by key** — each key carries a tier that sets its rate limit.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import threading
import time
from typing import Any

from ..errors import VantiaError
from ..json_utils import atomic_write_json, load_json
from ..logging_config import utc_now

__all__ = [
    "KEY_PREFIX",
    "RATE_LIMITS",
    "create_key",
    "delete_key",
    "hash_key",
    "list_keys",
    "rate_limit_for",
    "resolve_key",
    "window_allowance",
]

LOGGER = logging.getLogger("vantia.public_api.keys")

STORE_VERSION = 1
KEY_PREFIX = "vantia_sk_"

#: Requests per minute by key tier (§16.4).
RATE_LIMITS = {"free": 10, "business": 100, "pro": 100}

_store_lock = threading.RLock()

# In-memory sliding-window rate limiter: key_hash -> list[timestamps].
_rate_hits: dict[str, list[float]] = {}
_rate_lock = threading.RLock()


def _default_dir() -> str:
    return os.environ.get("VANTIA_API_KEYS_DIR", os.path.join(".vantia", "api_keys"))


def _store_file() -> str:
    return os.path.join(_default_dir(), "api_keys.json")


def _load_all() -> dict[str, Any]:
    data = load_json(_store_file())
    if not isinstance(data, dict) or not isinstance(data.get("keys"), dict):
        return {"version": STORE_VERSION, "keys": {}}
    return data


def _save_all(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_store_file()), exist_ok=True)
    atomic_write_json(_store_file(), data)


def hash_key(raw: str) -> str:
    """SHA-256 hex of a raw API key (the only form we ever store)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def rate_limit_for(tier: str) -> int:
    """Requests/minute allowance for a key tier (default 10)."""
    return RATE_LIMITS.get(tier, RATE_LIMITS["free"])


def create_key(
    owner_email: str,
    *,
    name: str = "",
    tier: str = "free",
    rate_limit_per_min: int | None = None,
) -> dict[str, Any]:
    """Create an API key; returns the raw key **once** plus its record.

    The raw key is never stored — only its SHA-256 hash — so it cannot be
    recovered later (§16.1).
    """
    if not owner_email:
        raise VantiaError("owner_email is required", code="owner_email_required")
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = hash_key(raw)
    limit = rate_limit_per_min if rate_limit_per_min is not None else rate_limit_for(tier)
    with _store_lock:
        data = _load_all()
        record = {
            "id": key_hash[:16],
            "key_hash": key_hash,
            "owner_email": owner_email,
            "name": name or f"{tier} key",
            "tier": tier,
            "rate_limit_per_min": int(limit),
            "created_at": utc_now(),
            "last_used_at": None,
        }
        data["keys"][key_hash] = record
        _save_all(data)
    return {"key": raw, "record": _public(record)}


def _public(record: dict[str, Any]) -> dict[str, Any]:
    """Record without the hash (safe to return in listings)."""
    return {k: v for k, v in record.items() if k != "key_hash"}


def resolve_key(raw: str) -> dict[str, Any] | None:
    """Look up a key by its raw value; ``None`` when unknown/invalid."""
    if not raw:
        return None
    return _load_all()["keys"].get(hash_key(raw.strip()))


def list_keys() -> list[dict[str, Any]]:
    """All key records (hashes redacted), newest first."""
    rows = [_public(r) for r in _load_all()["keys"].values()]
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows


def delete_key(key_id: str) -> bool:
    """Revoke a key by its id; raises when unknown."""
    with _store_lock:
        data = _load_all()
        target = None
        for key_hash, record in data["keys"].items():
            if record.get("id") == key_id:
                target = key_hash
                break
        if target is None:
            raise VantiaError(f"api key {key_id!r} not found", code="api_key_not_found")
        del data["keys"][target]
        _save_all(data)
    return True


def window_allowance(
    key_hash: str, limit: int, *, now: float | None = None
) -> tuple[bool, dict[str, int]]:
    """Sliding-window check: ``(allowed, {limit, remaining, reset})``.

    Records the hit when allowed. One-minute window; process-local (a cold
    Render instance resets it — acceptable for the documented limits).
    """
    current = now if now is not None else time.time()
    window_start = current - 60.0
    with _rate_lock:
        hits = [t for t in _rate_hits.get(key_hash, []) if t > window_start]
        if len(hits) >= limit:
            retry_after = int(max(1, 60 - (current - hits[0])))
            _rate_hits[key_hash] = hits
            return False, {"limit": limit, "remaining": 0, "reset": retry_after}
        hits.append(current)
        _rate_hits[key_hash] = hits
        return True, {"limit": limit, "remaining": max(0, limit - len(hits)), "reset": 60}
