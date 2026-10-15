"""Platform chatbot unit tests: tier daily rate limits and validation."""

from __future__ import annotations

import pytest

from engine.chat import MessageRateLimitExceeded, CHAT_RATE_LIMITS, chat
from engine.credits import default_ledger, reset_default_ledger, set_tier

_USER = "u-chat-test"


def _fake_llm(history, user_message, *, run_id):
    return "That's a great question about Vantia."


def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("VANTIA_CHAT_DIR", str(tmp_path / "chat"))
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path / "credits"))
    reset_default_ledger()
    monkeypatch.setattr("engine.chat._call_llm", _fake_llm)
    # Never hit the network in unit tests; the mirror is best-effort anyway.
    monkeypatch.setattr("engine.chat._mirror_to_supabase", lambda rows: None)


def test_free_tier_daily_message_limit(tmp_path, monkeypatch):
    _isolated(monkeypatch, tmp_path)
    try:
        set_tier(default_ledger(), _USER, "free")
        limit = CHAT_RATE_LIMITS["free"]
        for i in range(limit):
            result = chat(_USER, f"message {i}")
            assert result["status"] == "ok"
            assert result["used_today"] == i + 1
        with pytest.raises(MessageRateLimitExceeded) as exc:
            chat(_USER, "one too many")
        assert exc.value.code == "rate_limited"
        assert exc.value.context["tier"] == "free"
        assert exc.value.context["used"] == limit
    finally:
        reset_default_ledger()


def test_pro_tier_daily_message_limit(tmp_path, monkeypatch):
    _isolated(monkeypatch, tmp_path)
    try:
        set_tier(default_ledger(), _USER, "pro")
        limit = CHAT_RATE_LIMITS["pro"]
        for i in range(limit):
            result = chat(_USER, f"message {i}")
            assert result["status"] == "ok"
        with pytest.raises(MessageRateLimitExceeded):
            chat(_USER, "one too many")
    finally:
        reset_default_ledger()


def test_business_tier_is_unlimited(tmp_path, monkeypatch):
    _isolated(monkeypatch, tmp_path)
    try:
        set_tier(default_ledger(), _USER, "business")
        for i in range(250):
            result = chat(_USER, f"message {i}")
            assert result["status"] == "ok"
            assert result["limit"] is None
    finally:
        reset_default_ledger()


def test_unknown_user_defaults_to_free_limit(tmp_path, monkeypatch):
    _isolated(monkeypatch, tmp_path)
    try:
        # No explicit tier set -> free (20/day).
        limit = CHAT_RATE_LIMITS["free"]
        for i in range(limit):
            chat(_USER, f"message {i}")
        with pytest.raises(MessageRateLimitExceeded):
            chat(_USER, "one too many")
    finally:
        reset_default_ledger()


def test_message_required(tmp_path, monkeypatch):
    _isolated(monkeypatch, tmp_path)
    try:
        set_tier(default_ledger(), _USER, "free")
        with pytest.raises(MessageRateLimitExceeded.__bases__[0]) as exc:
            chat(_USER, "")
        assert exc.value.code == "message_required"
    finally:
        reset_default_ledger()


def test_user_id_required(tmp_path, monkeypatch):
    _isolated(monkeypatch, tmp_path)
    try:
        set_tier(default_ledger(), _USER, "free")
        with pytest.raises(MessageRateLimitExceeded.__bases__[0]) as exc:
            chat("", "hello")
        assert exc.value.code == "user_id_required"
    finally:
        reset_default_ledger()
