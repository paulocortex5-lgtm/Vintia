"""Quota tracker tests: daily rollover, rpd/rpm caps, mirrors, snapshots.

Task 1.6 acceptance: the router skips quota-exhausted providers; the
tracker must be the local source of truth (R28) and degrade gracefully
when Supabase is unreachable (§0.7). No Supabase, no network.
"""

import json

from engine.llm.quota import QuotaTracker, _today


def _tracker(tmp_path, **kwargs) -> QuotaTracker:
    # Tiny rpd so the cap is easy to hit; high rpm so only rpd bites.
    return QuotaTracker(cache_dir=tmp_path, limits={"rpd": 2, "rpm": 100}, **kwargs)


def test_increment_then_check_quota(tmp_path):
    tracker = _tracker(tmp_path)
    assert tracker.check_quota("groq")
    tracker.increment_usage("groq", 10, 5, now_ts=0.0)
    assert tracker.check_quota("groq")
    tracker.increment_usage("groq", 10, 5, now_ts=0.0)
    # second request hits rpd=2 -> provider is now exhausted
    assert not tracker.check_quota("groq")
    assert tracker.remaining_rpd("groq") == 0


def test_remaining_rpd_for_unused_provider(tmp_path):
    tracker = _tracker(tmp_path)
    assert tracker.remaining_rpd("nobody_used") == 2


def test_rpm_cap_blocks_a_burst(tmp_path):
    tracker = QuotaTracker(cache_dir=tmp_path, limits={"rpd": 1000, "rpm": 2})
    tracker.increment_usage("cerebras", 5, 5, now_ts=1000.0)
    tracker.increment_usage("cerebras", 5, 5, now_ts=1000.5)  # same minute window
    assert not tracker.check_quota("cerebras")  # last_minute(2) >= rpm(2)


def test_daily_rollover_resets_counters(tmp_path):
    day_one = "2026-01-01T09:00:00Z"
    day_two = "2026-01-02T09:00:00Z"
    one = QuotaTracker(cache_dir=tmp_path, now=day_one, limits={"rpd": 1, "rpm": 100})
    one.increment_usage("groq", 1, 1, now_ts=0.0)
    assert not one.check_quota("groq")

    two = QuotaTracker(cache_dir=tmp_path, now=day_two, limits={"rpd": 1, "rpm": 100})
    assert two.check_quota("groq")  # counters rolled over with the day


def test_reset_daily_quotas_clears_current_day(tmp_path):
    tracker = _tracker(tmp_path)
    tracker.increment_usage("groq", 1, 1, now_ts=0.0)
    tracker.increment_usage("groq", 1, 1, now_ts=0.0)
    assert not tracker.check_quota("groq")
    cleared = tracker.reset_daily_quotas()
    assert cleared == 1
    assert tracker.check_quota("groq")


def test_usage_snapshot_is_json_safe(tmp_path):
    tracker = _tracker(tmp_path)
    tracker.increment_usage("groq", 42, 7, now_ts=0.0)
    snap = tracker.usage_snapshot()
    json.dumps(snap)  # must serialise
    entry = snap["providers"]["groq"]
    assert entry["requests"] == 1
    assert entry["tokens_in"] == 42
    assert entry["tokens_out"] == 7
    assert entry["remaining_rpd"] == 1
    assert snap["date"] == _today()


def test_supabase_mirror_failure_does_not_break_calls(tmp_path):
    class _BrokenClient:
        def log_llm_usage(self, row):
            raise RuntimeError("supabase down")

    tracker = _tracker(tmp_path)
    tracker.set_supabase(_BrokenClient())  # inject a failing mirror
    row = tracker.increment_usage("groq", 1, 1, now_ts=0.0)
    assert row["provider"] == "groq"
    assert row["tokens_in"] == 1
    # local cache is authoritative regardless of the mirror failure
    assert tracker.check_quota("groq")


def test_cache_file_roundtrips(tmp_path):
    tracker = _tracker(tmp_path)
    tracker.increment_usage("groq", 3, 4, now_ts=0.0)
    raw = json.loads((tmp_path / "usage.json").read_text())
    assert raw["providers"]["groq"]["requests"] == 1
    assert raw["providers"]["groq"]["tokens_in"] == 3

    fresh = QuotaTracker(cache_dir=tmp_path, limits={"rpd": 100, "rpm": 100})
    assert fresh.remaining_rpd("groq") == 99  # rpd 100 - 1 already used


def test_injected_registry_supplies_limits(tmp_path, monkeypatch):
    from engine.llm.router import LLMModel, LLMProvider, LLMRegistry

    model = LLMModel(id="m")
    provider = LLMProvider(
        id="stub",
        display="Stub",
        tier="free",
        base_url="https://x/api",
        models=[model],
        limits={"rpd": 3, "rpm": 10},
    )
    registry = LLMRegistry([provider], {"free_only": ["free"]}, tmp_path / "providers.yaml")

    tracker = QuotaTracker(cache_dir=tmp_path, now="2026-01-01T00:00:00Z").with_registry(registry)
    tracker.increment_usage("stub", 1, 1, now_ts=0.0)
    tracker.increment_usage("stub", 1, 1, now_ts=0.0)
    tracker.increment_usage("stub", 1, 1, now_ts=0.0)
    assert not tracker.check_quota("stub")  # 3 == rpd from the registry
