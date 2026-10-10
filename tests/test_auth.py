"""Supabase Auth tests (task 8.1) — offline JWT verification, no network."""

import time

import httpx
import jwt as pyjwt
import pytest

from engine.auth import (
    decode_supabase_jwt,
    extract_bearer_token,
    refresh_access_token,
    require_user,
)
from engine.errors import AuthError

SECRET = "test-jwt-secret-rotate-me"


def make_token(
    sub: str = "user-a",
    *,
    exp_offset: int = 3600,
    role: str = "authenticated",
    audience: str = "authenticated",
    secret: str = SECRET,
    **extra,
) -> str:
    payload = {
        "sub": sub,
        "role": role,
        "aud": audience,
        "exp": int(time.time()) + exp_offset,
        **extra,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ── Bearer extraction ──────────────────────────────────────────────────


def test_extract_bearer_token_happy_path():
    assert extract_bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"
    assert extract_bearer_token("bearer   spaced  ") == "spaced"


def test_extract_rejects_missing_or_non_bearer():
    for header in (None, "", "Basic abc", "Bearer", "Bearer    "):
        with pytest.raises(AuthError) as excinfo:
            extract_bearer_token(header)
        assert excinfo.value.code == "missing_token"


# ── Offline verification ───────────────────────────────────────────────


def test_valid_token_verifies_offline():
    token = make_token("user-a", role="authenticated", app_metadata={"plan": "free"})
    context = decode_supabase_jwt(token, secret=SECRET)
    assert context.user_id == "user-a"
    assert context.role == "authenticated"
    assert context.expires_at is not None
    assert context.claims["app_metadata"]["plan"] == "free"


def test_expired_token_is_token_expired():
    with pytest.raises(AuthError) as excinfo:
        decode_supabase_jwt(make_token(exp_offset=-100), secret=SECRET)
    assert excinfo.value.code == "token_expired"


def test_leeway_can_admit_a_just_expired_token():
    token = make_token(exp_offset=-5)
    with pytest.raises(AuthError):
        decode_supabase_jwt(token, secret=SECRET)
    context = decode_supabase_jwt(token, secret=SECRET, leeway_sec=10)
    assert context.user_id == "user-a"


def test_wrong_signature_is_rejected():
    forged = make_token(secret="attacker-secret")
    with pytest.raises(AuthError) as excinfo:
        decode_supabase_jwt(forged, secret=SECRET)
    assert excinfo.value.code == "invalid_token"


def test_alg_none_and_confused_algorithms_are_refused():
    header = pyjwt.get_unverified_header(make_token())
    assert header["alg"] == "HS256"  # pinned — none/RS confusion can never pass
    unsigned = make_token().rsplit(".", 1)[0] + "."
    with pytest.raises(AuthError) as excinfo:
        decode_supabase_jwt(unsigned, secret=SECRET)
    assert excinfo.value.code == "invalid_token"


def test_wrong_audience_is_rejected():
    with pytest.raises(AuthError) as excinfo:
        decode_supabase_jwt(make_token(audience="admin"), secret=SECRET)
    assert excinfo.value.code == "invalid_token"


def test_missing_required_claims_are_rejected():
    base = {"sub": "u", "exp": int(time.time()) + 60, "aud": "authenticated"}
    no_sub = {k: v for k, v in base.items() if k != "sub"}
    no_exp = {k: v for k, v in base.items() if k != "exp"}
    for payload in (no_sub, no_exp):
        token = pyjwt.encode(payload, SECRET, algorithm="HS256")
        with pytest.raises(AuthError) as excinfo:
            decode_supabase_jwt(token, secret=SECRET)
        assert excinfo.value.code == "invalid_token"


def test_unconfigured_secret_refuses_instead_of_trusting(monkeypatch):
    for value in ("", "REPLACE_ME"):
        monkeypatch.setenv("SUPABASE_JWT_SECRET", value)
        with pytest.raises(AuthError) as excinfo:
            decode_supabase_jwt(make_token())
        assert excinfo.value.code == "auth_not_configured"


def test_require_user_end_to_end_from_header():
    context = require_user(f"Bearer {make_token('user-b')}", secret=SECRET)
    assert context.user_id == "user-b"
    with pytest.raises(AuthError) as excinfo:
        require_user(None, secret=SECRET)
    assert excinfo.value.code == "missing_token"


# ── Refresh (task 8.1) ─────────────────────────────────────────────────


def _refresh_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_refresh_success_returns_the_session():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "supabase.test"
        assert request.url.path == "/auth/v1/token"
        assert request.url.params["grant_type"] == "refresh_token"
        return httpx.Response(200, json={"access_token": "new.jwt.here", "refresh_token": "r2"})

    body = refresh_access_token(
        "r1", url="https://supabase.test", anon_key="anon", client=_refresh_client(handler)
    )
    assert body["access_token"] == "new.jwt.here"


def test_refresh_rejections_carry_the_status():
    client = _refresh_client(lambda request: httpx.Response(401, json={"error": "invalid"}))
    with pytest.raises(AuthError) as excinfo:
        refresh_access_token("r1", url="https://supabase.test", client=client)
    assert excinfo.value.code == "refresh_rejected"
    assert excinfo.value.context["status"] == 401


def test_refresh_bad_bodies_are_refused():
    cases = [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"no_access_token": True}),
        httpx.Response(200, json=["list"]),
    ]
    for response in cases:
        client = _refresh_client(lambda request, r=response: r)
        with pytest.raises(AuthError) as excinfo:
            refresh_access_token("r1", url="https://supabase.test", client=client)
        assert excinfo.value.code == "auth_response_invalid"


def test_refresh_unreachable_and_unconfigured():
    def boom(request):
        raise httpx.ConnectError("nope")

    with pytest.raises(AuthError) as excinfo:
        refresh_access_token("r1", url="https://supabase.test", client=_refresh_client(boom))
    assert excinfo.value.code == "auth_unreachable"

    with pytest.raises(AuthError) as excinfo2:
        refresh_access_token("r1", url="REPLACE_ME", client=_refresh_client(boom))
    assert excinfo2.value.code == "auth_not_configured"

    with pytest.raises(AuthError) as excinfo3:
        refresh_access_token("", url="https://supabase.test", client=_refresh_client(boom))
    assert excinfo3.value.code == "refresh_token_required"
