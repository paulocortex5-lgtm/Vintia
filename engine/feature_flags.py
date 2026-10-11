"""Feature flags (task 7.3) — deterministic, state-driven, honest defaults.

Rules (same shape as :mod:`engine.credits.config`):

* The authoritative state file decides: ``llm_policy.allow_paid`` →
  ``paid_llm``, ``credits.enabled`` → ``invoice_generation``,
  ``workspaces.enabled`` → ``workspace_ui``. The packaged seed is the
  documented fallback when no state file exists.
* A deployment may flip a flag with ``VANTIA_FLAG_<NAME>=1|0`` — an
  invalid value raises ``flag_value_invalid`` loudly instead of guessing.
* Unknown flags are **off** and reported as unknown — a typo never
  switches a feature on (fail closed, never fail open).
* Flags are read-only views; mutating one is a state change through the
  normal state manager, never a side effect of reading.
"""

from __future__ import annotations

import os
from typing import Any

from .errors import VantiaError
from .json_utils import load_json
from .state_manager import DEFAULT_STATE_DIR, VantiaState, seed_path

__all__ = ["KNOWN_FLAGS", "flags", "is_enabled"]

#: Every flag this platform knows. Anything else is unknown → off.
KNOWN_FLAGS = ("paid_llm", "invoice_generation", "workspace_ui")


def _load_state(state_dir: str | None = None) -> dict[str, Any]:
    try:
        data = VantiaState(state_dir or DEFAULT_STATE_DIR).load()
    except Exception:  # noqa: BLE001 — missing/corrupt state falls back to the seed
        data = load_json(seed_path())
    return data if isinstance(data, dict) else {}


def _as_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(raw)


def _state_value(state: dict[str, Any], flag: str) -> bool:
    """The flag's resting value in state (block missing → off, never on)."""
    if flag == "paid_llm":
        policy = state.get("llm_policy")
        return bool(isinstance(policy, dict) and policy.get("allow_paid"))
    if flag == "invoice_generation":
        credits = state.get("credits")
        return bool(isinstance(credits, dict) and credits.get("enabled"))
    if flag == "workspace_ui":
        workspaces = state.get("workspaces")
        return bool(isinstance(workspaces, dict) and workspaces.get("enabled"))
    return False  # pragma: no cover — unreachable for KNOWN_FLAGS


def flags(
    *, state_dir: str | None = None, environ: dict[str, str] | None = None
) -> dict[str, bool]:
    """Resolved snapshot of every known flag (env override wins over state)."""
    state = _load_state(state_dir)
    env = os.environ if environ is None else environ
    resolved: dict[str, bool] = {}
    for name in KNOWN_FLAGS:
        value = _state_value(state, name)
        env_name = f"VANTIA_FLAG_{name.upper()}"
        raw = env.get(env_name)
        if raw not in (None, ""):
            try:
                value = _as_bool(raw)
            except ValueError as exc:
                raise VantiaError(
                    f"{env_name}={raw!r} is not a valid boolean",
                    code="flag_value_invalid",
                    env=env_name,
                ) from exc
        resolved[name] = value
    return resolved


def is_enabled(
    name: str, *, state_dir: str | None = None, environ: dict[str, str] | None = None
) -> bool:
    """True only when the *known* flag ``name`` resolves on — unknown → False."""
    return bool(flags(state_dir=state_dir, environ=environ).get(name, False))
