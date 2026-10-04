"""Router tests: registry parsing, key filtering, quota filtering, chain order.

Covers task 1.6 acceptance: the router skips providers with no API key,
skips quota-exhausted providers, and preserves file order (free before
paid, R27). No network, no real keys — the environment is injected.
"""

import pytest

from engine.errors import LLMProviderFailure
from engine.llm.quota import QuotaTracker
from engine.llm.router import (
    LLMModel,
    LLMProvider,
    LLMRegistry,
    load_registry,
    pick,
    providers_summary,
    registry_for,
)

# Provider -> env var, as declared in providers.yaml
KEYS = {
    "nvidia_nim": "NVIDIA_NIM_API_KEY",
    "groq": "GROQ_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def test_load_registry_parses_every_provider():
    registry = load_registry()
    stats = registry.stats()
    assert stats["providers"] == 22
    assert stats["free"] == 12
    assert stats["paid"] == 10
    assert stats["models"] >= 40


def test_every_provider_resolves_a_default_model():
    registry = load_registry()
    for provider in registry:
        assert isinstance(provider.default_model, LLMModel)
        assert provider.resolve_url(provider.default_model)
        headers = provider.build_headers(provider.default_model)
        assert headers["User-Agent"].startswith("Vantia/")


def test_pick_returns_empty_when_no_keys_are_configured(tmp_path):
    assert (
        pick(profile="free_only", environ={}, quota_tracker=QuotaTracker(cache_dir=tmp_path)) == []
    )


def test_pick_skips_providers_without_a_key(tmp_path):
    tracker = QuotaTracker(cache_dir=tmp_path)
    chain = pick(
        profile="free_only",
        environ={"GROQ_API_KEY": "gsk_test_key", "CEREBRAS_API_KEY": ""},
        quota_tracker=tracker,
    )
    assert [p.id for p in chain] == ["groq"]  # cerebras key present but empty


def test_pick_preserves_registry_order(tmp_path):
    environ = {"GROQ_API_KEY": "gsk", "NVIDIA_NIM_API_KEY": "nv", "CEREBRAS_API_KEY": "cb"}
    chain = pick(
        profile="free_only", environ=environ, quota_tracker=QuotaTracker(cache_dir=tmp_path)
    )
    assert [p.id for p in chain] == ["nvidia_nim", "groq", "cerebras"]


def test_pick_blocks_paid_tier_unless_allowed(tmp_path):
    environ = {"OPENAI_API_KEY": "sk_test", "GROQ_API_KEY": "gsk"}
    tracker = QuotaTracker(cache_dir=tmp_path)
    blocked = pick(profile="paid", environ=environ, quota_tracker=tracker, allow_paid=False)
    assert [p.id for p in blocked] == ["groq"]  # openai filtered out by allow_paid
    allowed = pick(profile="paid", environ=environ, quota_tracker=tracker, allow_paid=True)
    assert {p.id for p in allowed} == {"groq", "openai"}


def test_pick_skips_quota_exhausted_provider(tmp_path):
    environ = {"GROQ_API_KEY": "gsk", "CEREBRAS_API_KEY": "cb"}
    tracker = QuotaTracker(cache_dir=tmp_path, limits={"rpd": 1, "rpm": 100})
    tracker.increment_usage("groq", 10, 10, now_ts=0.0)  # exhaust the day's quota

    chain = pick(profile="free_only", environ=environ, quota_tracker=tracker)
    assert [p.id for p in chain] == ["cerebras"]


def test_pick_model_filter_limits_the_chain(tmp_path):
    environ = {"GROQ_API_KEY": "gsk", "NVIDIA_NIM_API_KEY": "nv"}
    chain = pick(
        profile="free_only",
        environ=environ,
        quota_tracker=QuotaTracker(cache_dir=tmp_path),
        model="llama-3.3-70b-versatile",  # a groq-only model id
    )
    assert [p.id for p in chain] == ["groq"]


def test_pick_rejects_an_unknown_profile():
    with pytest.raises(LLMProviderFailure, match="unknown profile"):
        pick(profile="does_not_exist", environ={}, quota_tracker=QuotaTracker(cache_dir="/tmp"))


def test_registry_rejects_duplicate_provider_ids():
    model = LLMModel(id="m1")
    provider = LLMProvider(
        id="dup", display="Dup", tier="free", base_url="https://x/api", models=[model]
    )
    with pytest.raises(LLMProviderFailure, match="duplicate provider id"):
        LLMRegistry([provider, provider], {"free_only": ["free"]}, __file__)


def test_registry_get_raises_for_unknown_provider():
    registry = LLMRegistry([], {"free_only": ["free"]}, __file__)
    with pytest.raises(LLMProviderFailure, match="unknown provider"):
        registry.get("nobody")


def test_registry_is_cached_per_path(tmp_path):
    import yaml

    raw = {
        "profiles": {"free_only": ["free"]},
        "providers": [
            {
                "id": "stub",
                "tier": "free",
                "base_url": "https://api.stub/v1/chat/completions",
                "api_key_env": "STUB_KEY",
                "models": [{"id": "stub-1"}],
            }
        ],
    }
    path = tmp_path / "providers.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    first = registry_for(path)
    second = registry_for(path)
    assert first is second
    assert len(first) == 1


def test_providers_summary_reports_key_presence(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk")
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    summary = providers_summary(profile="free_only", include="all")
    by_id = {row["id"]: row for row in summary}
    assert by_id["groq"]["available"] is True
    assert by_id["cerebras"]["available"] is False
    assert by_id["groq"]["tier"] == "free"
    assert by_id["groq"]["models"], "model list must not be empty"
    assert by_id["groq"]["limits"]["rpd"] > 0
