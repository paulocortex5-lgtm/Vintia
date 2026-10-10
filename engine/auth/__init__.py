"""Supabase Auth integration (task 8.1).

JWT extraction, verification and refresh for the workspace layer. The
token is verified **offline** against ``SUPABASE_JWT_SECRET`` (HS256 — the
only algorithm accepted; ``none``/RS/ES are refused as invalid), so no
network call sits between a request and its identity check.
"""

from __future__ import annotations

from .jwt_auth import (
    AuthContext,
    decode_supabase_jwt,
    extract_bearer_token,
    refresh_access_token,
    require_user,
)

__all__ = [
    "AuthContext",
    "decode_supabase_jwt",
    "extract_bearer_token",
    "refresh_access_token",
    "require_user",
]
