"""Credit configuration loader (task 11.1 support).

The tier allowances, credit packs and per-operation token costs live in the
authoritative ``state.json`` under the ``credits`` key (packaged in
``engine/seed/state.json``). Nothing in this package hardcodes those numbers:
every price and allowance is read through :func:`load_credits_config` so a
deployment can re-price by editing state, and tests can inject a dict.

``.env.example``'s ``VANTIA_*`` credit variables are honoured as **overrides**
(12-factor style) — they were documented but unread before run 16; an invalid
value raises ``credits_config_invalid`` loudly instead of falling back
silently.

Fallback order: ``<state_dir>/state.json`` → packaged seed → env overlay. A
state file that exists but has no ``credits`` block returns ``{}`` (plus any
env overlay) — callers then fall back to their documented defaults instead of
silently using the seed's numbers.
"""

from __future__ import annotations

import os
from typing import Any

from ..errors import VantiaError
from ..json_utils import load_json
from ..state_manager import DEFAULT_STATE_DIR, VantiaState, seed_path

__all__ = ["load_credits_config"]


def _as_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(raw)


#: env var → (config key, caster). Documented in ``.env.example``.
_ENV_OVERRIDES: dict[str, tuple[str, Any]] = {
    "VANTIA_CREDITS_ENABLED": ("enabled", _as_bool),
    "VANTIA_FREE_TIER_TOKENS": ("free_tier_tokens", int),
    "VANTIA_PRO_TIER_TOKENS": ("pro_tier_tokens", int),
    "VANTIA_BUSINESS_TIER_TOKENS": ("business_tier_tokens", int),
}


def _apply_env_overrides(credits: dict[str, Any]) -> dict[str, Any]:
    for env_name, (key, caster) in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_name)
        if raw is None or raw == "":
            continue
        try:
            credits[key] = caster(raw)
        except ValueError as exc:
            raise VantiaError(
                f"{env_name}={raw!r} is not a valid {caster.__name__}",
                code="credits_config_invalid",
                env=env_name,
            ) from exc
    return credits


def load_credits_config(state_dir: str | None = None) -> dict[str, Any]:
    """Return the ``credits`` block of the current state, env-overlaid."""
    try:
        data = VantiaState(state_dir or DEFAULT_STATE_DIR).load()
    except Exception:  # noqa: BLE001 — missing/corrupt state falls back to the seed
        data = load_json(seed_path())
    if not isinstance(data, dict):
        return {}
    credits = data.get("credits")
    return _apply_env_overrides(dict(credits)) if isinstance(credits, dict) else {}
