"""Referral program tests (task 15.11 §15.5).

Offline: ``$VANTIA_REFERRALS_DIR`` + ``$VANTIA_CREDITS_DIR`` isolated to
``tmp_path``. Covers code generation/stability/uniqueness, both-party
crediting, idempotency (no double credit), self-referral refusal, unknown
code, and history isolation.
"""

import pytest

from engine.credits.ledger import CreditLedger, reset_default_ledger
from engine.referrals import manager


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_REFERRALS_DIR", str(tmp_path / "referrals"))
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path / "credits"))
    reset_default_ledger()
    return manager


def _ledger():
    return CreditLedger()


def test_generate_code_is_stable(env):
    code1 = env.generate_code("u1")
    code2 = env.generate_code("u1")
    assert code1 == code2
    assert len(code1) == 8


def test_codes_are_unique(env):
    codes = {env.generate_code(f"u{i}") for i in range(50)}
    assert len(codes) == 50


def test_referrer_for_code_roundtrip(env):
    code = env.generate_code("u1")
    assert env.referrer_for_code(code) == "u1"
    assert env.referrer_for_code(code.lower()) == "u1"  # case-insensitive
    assert env.referrer_for_code("NOPE123") is None


def test_signup_credits_both_parties(env, tmp_path, monkeypatch):
    ledger = _ledger()
    code = env.generate_code("referrer")
    row = env.record_signup(code, "referee", "referee@example.com", ledger=ledger)
    assert row["credited"] is True
    assert row["status"] == "completed"
    assert ledger.balance("referrer") == manager.REFERRAL_BONUS
    assert ledger.balance("referee") == manager.REFERRAL_BONUS


def test_signup_is_idempotent_no_double_credit(env):
    ledger = _ledger()
    code = env.generate_code("referrer")
    first = env.record_signup(code, "referee", ledger=ledger)
    second = env.record_signup(code, "referee", ledger=ledger)
    assert first["credited"] is True
    assert second["credited"] is False
    # Referee credited exactly once.
    assert ledger.balance("referee") == manager.REFERRAL_BONUS
    assert ledger.balance("referrer") == manager.REFERRAL_BONUS


def test_self_referral_refused(env):
    ledger = _ledger()
    code = env.generate_code("u1")
    with pytest.raises(env.VantiaError) as exc:
        env.record_signup(code, "u1", ledger=ledger)
    assert exc.value.code == "self_referral"
    assert ledger.balance("u1") == 0


def test_unknown_code_refused(env):
    ledger = _ledger()
    with pytest.raises(env.VantiaError) as exc:
        env.record_signup("BADCODE1", "referee", ledger=ledger)
    assert exc.value.code == "referral_code_invalid"


def test_history_is_isolated(env):
    ledger = _ledger()
    c1 = env.generate_code("referrer1")
    c2 = env.generate_code("referrer2")
    env.record_signup(c1, "ref-a", ledger=ledger)
    env.record_signup(c2, "ref-b", ledger=ledger)
    assert len(env.history_for("referrer1")) == 1
    assert len(env.history_for("referrer2")) == 1
    assert env.history_for("referrer1")[0]["referee_id"] == "ref-a"


def test_missing_fields_refused(env):
    with pytest.raises(env.VantiaError):
        env.record_signup("", "referee")
