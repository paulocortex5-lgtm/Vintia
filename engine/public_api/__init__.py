"""Public API for universities (task 15.12)."""

from .keys import (
    KEY_PREFIX,
    RATE_LIMITS,
    create_key,
    delete_key,
    hash_key,
    list_keys,
    rate_limit_for,
    resolve_key,
    window_allowance,
)

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
