"""Credit configuration loader (task 11.1 support).

The tier allowances, credit packs and per-operation token costs live in the
authoritative ``state.json`` under the ``credits`` key (packaged in
``engine/seed/state.json``). Nothing in this package hardcodes those numbers:
every price and allowance is read through :func:`load_credits_config` so a
deployment can re-price by editing state, and tests can inject a dict.

Fallback order: ``<state_dir>/state.json`` → packaged seed. A state file that
exists but has no ``credits`` block returns ``{}`` — callers then fall back to
their documented defaults instead of silently using the seed's numbers.
"""

from __future__ import annotations

from typing import Any

from ..json_utils import load_json
from ..state_manager import DEFAULT_STATE_DIR, VantiaState, seed_path

__all__ = ["load_credits_config"]


def load_credits_config(state_dir: str | None = None) -> dict[str, Any]:
    """Return the ``credits`` block of the current state (``{}`` if absent)."""
    try:
        data = VantiaState(state_dir or DEFAULT_STATE_DIR).load()
    except Exception:  # noqa: BLE001 — missing/corrupt state falls back to the seed
        data = load_json(seed_path())
    if not isinstance(data, dict):
        return {}
    credits = data.get("credits")
    return dict(credits) if isinstance(credits, dict) else {}
