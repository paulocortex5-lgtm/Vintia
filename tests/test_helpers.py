"""Helper-module tests: JSON I/O, logging, retries, circuit breaker, errors."""

import json

from engine.errors import (
    CircuitOpenError,
    InsufficientCredits,
    StripeError,
    VantiaError,
)
from engine.hash_chain import HashChain
from engine.json_utils import atomic_write_json, load_json
from engine.logging_config import JsonLineFormatter, configure_logging, get_run_id, log_data, utc_now
from engine.retry import CircuitBreaker, retry_with_backoff


# ── v4.0 error taxonomy (§14) ─────────────────────────────────────────


def test_error_codes_and_serialisation():
    for error in [VantiaError("base"), InsufficientCredits(10000, 80000), StripeError("checkout failed")]:
        assert error.message
        assert isinstance(error.code, str)
        assert "error" in error.as_dict()
    assert InsufficientCredits(1, 2).context == {"balance": 1, "required": 2}
    assert InsufficientCredits(10000, 80000).code == "insufficient_credits"
    assert StripeError("x").code == "stripe_error"


# ── JSON helpers ──────────────────────────────────────────────────────


def test_json_atomic_roundtrip(tmp_path):
    path = tmp_path / "deep" / "nested" / "data.json"
    payload = {"tasks": {"0.1": {"status": "complete"}}, "run_count": 1}
    atomic_write_json(str(path), payload)
    assert path.parent.exists()
    assert load_json(str(path)) == payload
    assert list(tmp_path.glob(".tmp-*")) == [], "temp files must be cleaned up"


def test_load_json_missing_returns_default(tmp_path):
    assert load_json(str(tmp_path / "absent.json")) is None
    assert load_json(str(tmp_path / "absent.json"), default=[]) == []


def test_utc_now_is_zulu():
    assert utc_now().endswith("Z")


# ── logging ───────────────────────────────────────────────────────────


def test_log_data_emits_json_with_run_id(tmp_path, capsys):
    import logging

    configure_logging(level="DEBUG", run_id="testrun1")
    logger = logging.getLogger("vantia.test")
    log_data(logger, logging.INFO, "task completed", task_id="0.3", artifacts=["a.py"])
    line = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(line)
    assert record["level"] == "INFO"
    assert record["logger"] == "vantia.test"
    assert record["run_id"] == "testrun1"
    assert record["msg"] == "task completed"
    assert record["data"] == {"task_id": "0.3", "artifacts": ["a.py"]}
    assert "ts" in record
    assert get_run_id() == "testrun1"
    configure_logging(level="INFO", run_id="testrun2")


def test_formatter_is_json_lines():
    import logging

    formatter = JsonLineFormatter()
    record = logging.makeLogRecord({"msg": "hello", "levelno": 20, "levelname": "INFO", "name": "vantia"})
    formatter.format(record)
    parsed = json.loads(formatter.format(record))
    assert parsed["msg"] == "hello"


# ── retry + circuit breaker (§14) ─────────────────────────────────────


def test_retry_succeeds_after_transient_failures():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise VantiaError("boom")
        return "ok"

    sleeps = []
    assert retry_with_backoff(flaky, attempts=5, sleep=sleeps.append) == "ok"
    assert calls["n"] == 3
    assert len(sleeps) == 2
    assert all(delay >= 0 for delay in sleeps)


def test_retry_gives_up_and_raises():
    def always_fail():
        raise VantiaError("always")

    try:
        retry_with_backoff(always_fail, attempts=3, sleep=lambda _d: None)
        assert False, "expected VantiaError"
    except VantiaError:
        pass


def test_retry_skips_non_retryable_exceptions():
    try:
        retry_with_backoff(lambda: 1 / 0, attempts=3, sleep=lambda _d: None)
        assert False, "expected ZeroDivisionError"
    except ZeroDivisionError:
        pass


def test_circuit_breaker_opens_and_recovers():
    now = {"t": 0.0}
    breaker = CircuitBreaker(
        failure_threshold=3, reset_after_sec=100.0, clock=lambda: now["t"]
    )
    assert breaker.state == "closed"
    breaker.allow()
    for _ in range(2):
        breaker.record_failure()
    assert breaker.state == "closed"
    breaker.record_failure()
    assert breaker.state == "open"
    try:
        breaker.allow()
        assert False, "expected CircuitOpenError"
    except CircuitOpenError as exc:
        assert exc.code == "circuit_open"

    now["t"] = 101.0
    assert breaker.state == "half_open"
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == "open"
    now["t"] = 250.0
    assert breaker.state == "half_open"
    breaker.record_success()
    assert breaker.state == "closed"


# ── hash chain round-trip through the state manager ───────────────────


def test_hash_chain_verifies_a_real_sequence(tmp_path):
    chain = HashChain(str(tmp_path / "chain.json"))
    for index in range(5):
        chain.append({"event": "task_complete", "task_id": f"0.{index}"})
    assert chain.length == 5
    assert chain.verify() == (True, 5)
