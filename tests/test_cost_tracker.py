"""Tests for ``engine/cost_tracker.py`` — the JSONL cost ledger."""

import json

from engine.cost_tracker import CostTracker


def test_empty_ledger_has_zero_totals(tmp_path):
    tracker = CostTracker(str(tmp_path / "costs.jsonl"))
    assert tracker.total_usd() == 0.0
    assert tracker.tokens() == (0, 0)


def test_ledger_roundtrip_and_filtering(tmp_path):
    tracker = CostTracker(str(tmp_path / "costs.jsonl"))
    tracker.log_llm_call(
        provider="groq",
        model="llama-3.3-70b",
        tokens_in=1000,
        tokens_out=500,
        usd=0.002,
        task_id="1.7",
        run_id="1",
    )
    tracker.log_llm_call(
        provider="nvidia_nim",
        model="llama-3.3-70b",
        tokens_in=2000,
        tokens_out=100,
        usd=0.001,
        task_id="1.7",
        run_id="2",
    )
    assert tracker.total_usd() == 0.003
    assert tracker.tokens() == (3000, 600)
    assert tracker.total_usd(run_id="1") == 0.002
    assert tracker.tokens(run_id="1") == (1000, 500)
    assert tracker.total_usd(run_id="3") == 0.0


def test_each_event_is_a_separate_jsonl_line(tmp_path):
    ledger = tmp_path / "costs.jsonl"
    tracker = CostTracker(str(ledger))
    tracker.log_llm_call(provider="groq", model="m", tokens_in=1, tokens_out=1)
    tracker.log_llm_call(provider="groq", model="m", tokens_in=1, tokens_out=1)
    lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 2
    event = json.loads(lines[0])
    assert event["kind"] == "llm_call"
    assert event["provider"] == "groq"
    assert event["ts"]


def test_budget_status_warns_then_exhausts(tmp_path):
    tracker = CostTracker(str(tmp_path / "costs.jsonl"), max_usd=10.0, warn_at_pct=0.8)
    status = tracker.budget_status()
    assert status["budget_usd"] == 10.0
    assert status["warn_threshold_usd"] == 8.0
    assert not status["warning"]
    assert not status["exhausted"]

    tracker.log_llm_call(provider="groq", model="m", tokens_in=1, tokens_out=1, usd=8.1)
    status = tracker.budget_status()
    assert status["warning"]
    assert not status["exhausted"]

    tracker.log_llm_call(provider="groq", model="m", tokens_in=1, tokens_out=1, usd=2.0)
    assert tracker.budget_status()["exhausted"]


def test_zero_budget_never_warns(tmp_path):
    tracker = CostTracker(str(tmp_path / "costs.jsonl"), max_usd=0.0)
    tracker.log_llm_call(provider="groq", model="m", tokens_in=1, tokens_out=1, usd=5.0)
    status = tracker.budget_status()
    assert not status["warning"]
    assert not status["exhausted"]
    assert status["used_usd"] == 5.0
