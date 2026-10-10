"""JWT extraction, verification and refresh (task 8.1 core).

Security posture (repo honesty rules):

* **Offline verification** — HS256 against ``SUPABASE_JWT_SECRET``; the
  only accepted algorithm is HS256 (pinned), so algorithm-confusion
  (``none``, RS256-with-HS256 key confusion) is impossible.
* **Loud when unconfigured** — a missing/placeholder secret raises
  ``auth_not_configured`` instead of skipping verification. There is no
  "trust the header" fallback anywhere.
* **Expiry is enforced** — an expired token is ``token_expired``, never a
  soft pass; ``sub`` and ``exp`` are required claims.
* **Refresh goes to Supabase only** — ``POST {SUPABASE_URL}/auth/v1/
  token?grant_type=refresh_token`` with the project anon key; failures
  (4xx/5xx, unreachable, malformed body) raise stable codes and never
  return a half-parsed session.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from jwt import InvalidTokenError

from ..errors import AuthError

__all__ = [
    "AuthContext",
    "decode_supabase_jwt",
    "extract_bearer_token",
    "refresh_access_token",
    "require_user",
]

#: The audience Supabase stamps on every access token.
SUPABASE_AUDIENCE = "authenticated"

_PLACEHOLDER = "REPLACE_ME"


@dataclass(frozen=True)
class AuthContext:
    """Verified identity of one request (task 8.1)."""

    user_id: str
    role: str
    expires_at: int | None
    claims: dict[str, Any] = field(default_factory=dict)


def extract_bearer_token(authorization: str | None) -> str:
    """Pull the token out of an ``Authorization: Bearer <jwt>`` header."""
    if not authorization:
        raise AuthError("Authorization header is missing", code="missing_token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("Authorization must be 'Bearer <token>'", code="missing_token")
    return token.strip()


def _configured_secret(secret: str | None) -> str:
    resolved = secret if secret is not None else os.environ.get("SUPABASE_JWT_SECRET", "")
    if not resolved or resolved == _PLACEHOLDER:
        raise AuthError(
            "SUPABASE_JWT_SECRET is not configured; refusing to trust unverified tokens",
            code="auth_not_configured",
        )
    return resolved


def decode_supabase_jwt(
    token: str,
    *,
    secret: str | None = None,
    audience: str = SUPABASE_AUDIENCE,
    leeway_sec: int = 0,
) -> AuthContext:
    """Verify ``token`` offline and return its :class:`AuthContext`."""
    key = _configured_secret(secret)
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=["HS256"],  # pinned — no algorithm confusion, ever
            audience=audience,
            leeway=leeway_sec,
            options={"require": ["exp", "sub"]},
        )
    except InvalidTokenError as exc:  # includes ExpiredSignatureError, InvalidAudienceError
        code = "token_expired" if isinstance(exc, jwt.ExpiredSignatureError) else "invalid_token"
        raise AuthError(f"token rejected: {exc}", code=code) from exc
    return AuthContext(
        user_id=str(claims["sub"]),
        role=str(claims.get("role") or audience),
        expires_at=int(claims["exp"]),
        claims=dict(claims),
    )


def require_user(authorization: str | None, *, secret: str | None = None) -> AuthContext:
    """One-call guard: header in, verified identity out (or AuthError)."""
    return decode_supabase_jwt(extract_bearer_token(authorization), secret=secret)


def refresh_access_token(
    refresh_token: str,
    *,
    url: str | None = None,
    anon_key: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Exchange a refresh token for a new session at Supabase Auth.

    Returns the raw session body (``access_token``, ``refresh_token``,
    ``expires_at``, …) — validated to actually contain an access token.
    Injectable ``client``/``url`` keep the tests fully offline.
    """
    base = (url if url is not None else os.environ.get("SUPABASE_URL", "")).rstrip("/")
    if not base or base == _PLACEHOLDER:
        raise AuthError("SUPABASE_URL is not configured", code="auth_not_configured")
    if not refresh_token:
        raise AuthError("refresh_token is required", code="refresh_token_required")
    api_key = anon_key if anon_key is not None else os.environ.get("SUPABASE_ANON_KEY", "")
    http = client if client is not None else httpx.Client(timeout=10.0)
    try:
        response = http.post(
            f"{base}/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": refresh_token},
            headers={"apikey": api_key, "Content-Type": "application/json"},
        )
    except httpx.HTTPError as exc:
        raise AuthError(f"supabase auth unreachable: {exc}", code="auth_unreachable") from exc
    finally:
        if client is None:
            http.close()
    if response.status_code >= 400:
        raise AuthError(
            f"refresh rejected with HTTP {response.status_code}",
            code="refresh_rejected",
            status=response.status_code,
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise AuthError("auth refresh returned non-JSON", code="auth_response_invalid") from exc
    if not isinstance(body, dict) or not body.get("access_token"):
        raise AuthError("auth refresh response has no access_token", code="auth_response_invalid")
    return body
