"""LLM client tests: payload shapes, failover, dry-run, budget, envelope.

Task 1.7 acceptance: fenced JSON is stripped by json_utils, retry/failover
works through the chain, all-providers-429 raises ProviderError
(AllProvidersExhausted), the dry run performs no network I/O (R25), and
the envelope is hash-chained (R24). No real provider calls.
"""

import hashlib

import httpx
import pytest

from engine.errors import (
    AllProvidersExhausted,
    BudgetExceeded,
    LLMEmptyResponseError,
    LLMError,
    LLMNetworkError,
    LLMProviderFailure,
    LLMTimeoutError,
)
from engine.json_utils import canonical_json
from engine.llm.client import (
    DRY_RUN_STUB,
    RETRYABLE,
    LLMClient,
    build_envelope,
    build_payload,
    extract_result,
)
from engine.llm.quota import QuotaTracker
from engine.llm.router import LLMModel, LLMProvider

MESSAGES = [{"role": "user", "content": "hello world"}]
OPENAI_OK = {
    "id": "gen-1",
    "choices": [{"message": {"content": "done"}}],
    "usage": {"prompt_tokens": 11, "completion_tokens": 22},
}


class FakeResponse:
    """Just enough of httpx.Response for the client."""

    def __init__(self, status_code: int = 200, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or str(self._payload)

    def json(self) -> dict:
        return self._payload


class FakeHTTP:
    """Recorded httpx.Client stand-in."""

    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if not self.responses:
            raise AssertionError("client made an unexpected request")
        return self.responses.pop(0)


def make_provider(
    provider_id: str = "groq",
    payload_style: str = "openai",
    in_price: float = 0.0,
    out_price: float = 0.0,
    model_id: str = "llama-3.3-70b-versatile",
) -> tuple[LLMProvider, LLMModel]:
    model = LLMModel(id=model_id, in_usd_per_mtok=in_price, out_usd_per_mtok=out_price)
    provider = LLMProvider(
        id=provider_id,
        display=provider_id,
        tier="free",
        base_url="https://api.example/v1/chat/completions",
        api_key_env="GROQ_API_KEY",
        payload_style=payload_style,
        models=[model],
    )
    return provider, model


# ── build_payload / extract_result ────────────────────────────────────


def test_build_payload_openai_shape():
    provider, model = make_provider()
    payload = build_payload(
        provider, model, MESSAGES, temperature=0.0, max_tokens=123, system="be terse"
    )
    assert payload["model"] == model.id
    assert payload["temperature"] == 0.0
    assert payload["max_tokens"] == 123
    assert [m["role"] for m in payload["messages"]] == ["system", "user"]
    assert payload["messages"][1]["content"] == "hello world"


def test_build_payload_defaults_max_tokens_from_model():
    provider, model = make_provider()
    assert build_payload(provider, model, MESSAGES)["max_tokens"] == model.max_tokens


def test_build_payload_anthropic_and_cohere_split_the_system_message():
    for style in ("anthropic", "cohere"):
        provider, model = make_provider(payload_style=style)
        payload = build_payload(provider, model, MESSAGES, system="be terse")
        assert payload["system"] == "be terse"
        assert payload["messages"] == [{"role": "user", "content": "hello world"}]


def test_build_payload_gemini_uses_contents():
    provider, model = make_provider(payload_style="gemini")
    payload = build_payload(provider, model, MESSAGES, system="be terse")
    assert "contents" in payload and "generationConfig" in payload
    assert payload["generationConfig"]["maxOutputTokens"] == model.max_tokens
    assert payload["contents"][0]["role"] == "user"  # system folded into the turn


def test_extract_result_parses_all_payload_styles():
    text, usage = extract_result(make_provider()[0], OPENAI_OK)
    assert text == "done" and usage == {"tokens_in": 11, "tokens_out": 22}

    text, usage = extract_result(
        make_provider(payload_style="cohere")[0],
        {
            "message": {"content": [{"text": "a"}, {"text": "b"}]},
            "usage": {"input_tokens": 5, "output_tokens": 6},
        },
    )
    assert text == "ab" and usage == {"tokens_in": 5, "tokens_out": 6}

    text, usage = extract_result(
        make_provider(payload_style="anthropic")[0],
        {
            "content": [{"text": "x"}, {"text": "y"}],
            "usage": {"input_tokens": 7, "output_tokens": 8},
        },
    )
    assert text == "xy" and usage["tokens_out"] == 8

    text, usage = extract_result(
        make_provider(payload_style="gemini")[0],
        {
            "candidates": [{"content": {"parts": [{"text": "z"}]}}],
            "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 10},
        },
    )
    assert text == "z" and usage == {"tokens_in": 9, "tokens_out": 10}


def test_extract_result_tolerates_a_missing_usage_block():
    text, usage = extract_result(make_provider()[0], {"choices": [{"message": {"content": "x"}}]})
    assert text == "x"
    assert usage == {"tokens_in": 0, "tokens_out": 0}


# ── single call ────────────────────────────────────────────────────────


def test_complete_returns_a_parsed_result(tmp_path):
    provider, model = make_provider()
    http = FakeHTTP(FakeResponse(200, OPENAI_OK))
    tracker = QuotaTracker(cache_dir=tmp_path)
    client = LLMClient(http_client=http, tracker=tracker)
    result = client.complete(provider, model, MESSAGES)

    assert result.text == "done"
    assert result.provider == "groq"
    assert result.model == model.id
    assert (result.tokens_in, result.tokens_out) == (11, 22)
    assert result.cost_usd == 0.0
    assert result.response_id == "gen-1"
    assert http.calls[0]["url"] == provider.base_url
    assert http.calls[0]["headers"]["User-Agent"].startswith("Vantia/")
    # R28 — the tracker learned about the call
    assert tracker.usage_snapshot()["providers"]["groq"]["requests"] == 1


def test_complete_prices_paid_models(tmp_path):
    provider, _ = make_provider(in_price=1.0, out_price=2.0)
    http = FakeHTTP(
        FakeResponse(
            200,
            {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
            },
        )
    )
    result = LLMClient(http_client=http).complete(provider, provider.default_model, MESSAGES)
    assert result.cost_usd == pytest.approx((1.0 * 1000 + 2.0 * 500) / 1_000_000.0)


def test_timeout_is_mapped_to_a_retryable_error(tmp_path):
    class _SlowHTTP:
        def post(self, *args, **kwargs):
            raise httpx.TimeoutException("too slow")

    provider, model = make_provider()
    client = LLMClient(http_client=_SlowHTTP())  # type: ignore[arg-type]
    with pytest.raises(LLMTimeoutError):
        client.complete(provider, model, MESSAGES)
    assert LLMTimeoutError in RETRYABLE


def test_network_error_is_retryable(tmp_path):
    class _DownHTTP:
        def post(self, *args, **kwargs):
            raise httpx.ConnectError("connection refused")

    provider, model = make_provider()
    with pytest.raises(LLMNetworkError):
        LLMClient(http_client=_DownHTTP()).complete(provider, model, MESSAGES)  # type: ignore[arg-type]
    assert LLMNetworkError in RETRYABLE


def test_empty_response_is_retryable(tmp_path):
    provider, model = make_provider()
    http = FakeHTTP(FakeResponse(200, {"choices": [{"message": {"content": "   "}}]}))
    with pytest.raises(LLMEmptyResponseError):
        LLMClient(http_client=http).complete(provider, model, MESSAGES)
    assert LLMEmptyResponseError in RETRYABLE


def test_http_400_surfaces_the_error_without_failover(tmp_path):
    provider, model = make_provider()
    http = FakeHTTP(FakeResponse(400, text="model not found"))
    with pytest.raises(LLMProviderFailure, match="400"):
        LLMClient(http_client=http).complete(provider, model, MESSAGES)


# ── dry run (R25) ─────────────────────────────────────────────────────


def test_dry_run_performs_no_network_io(tmp_path):
    provider, model = make_provider()
    http = FakeHTTP()
    client = LLMClient(http_client=http, tracker=QuotaTracker(cache_dir=tmp_path))
    result = client.complete(provider, model, MESSAGES, dry_run=True)
    assert result.text == DRY_RUN_STUB
    assert result.dry_run is True
    assert result.cost_usd == 0.0
    assert http.calls == []


def test_dry_run_env_var_short_circuits(monkeypatch):
    monkeypatch.setenv("VANTIA_DRY_RUN", "1")
    provider, model = make_provider()
    result = LLMClient(http_client=FakeHTTP()).complete(provider, model, MESSAGES)
    assert result.text == DRY_RUN_STUB
    assert result.cost_usd == 0.0


def test_explicit_dry_run_false_still_calls_the_network(tmp_path):
    provider, model = make_provider()
    http = FakeHTTP(FakeResponse(200, OPENAI_OK))
    LLMClient(http_client=http).complete(provider, model, MESSAGES, dry_run=False)
    assert len(http.calls) == 1


# ── failover (R35) ────────────────────────────────────────────────────


def test_run_chain_fails_over_after_a_429(tmp_path):
    first, first_model = make_provider(provider_id="groq")
    second, second_model = make_provider(provider_id="cerebras", model_id="llama3-70b")
    http = FakeHTTP(
        FakeResponse(429, text="rate limited"),
        FakeResponse(200, {"choices": [{"message": {"content": "fallback answer"}}]}),
    )
    client = LLMClient(http_client=http)
    result = client.run_chain([(first, first_model), (second, second_model)], MESSAGES)
    assert result.provider == "cerebras"
    assert result.text == "fallback answer"


def test_run_chain_raises_all_providers_exhausted_on_all_429s(tmp_path):
    chain = [make_provider(provider_id=f"p{i}", model_id=f"m{i}") for i in range(3)]
    http = FakeHTTP(*(FakeResponse(429) for _ in chain))
    with pytest.raises(AllProvidersExhausted) as excinfo:
        LLMClient(http_client=http).run_chain(chain, MESSAGES)
    assert len(excinfo.value.attempts) == 3
    assert "429" in excinfo.value.attempts[0]
    # Every 429 becomes an LLMProviderFailure, which run_chain treats as
    # retryable, so a nested chain keeps failing over before giving up.
    assert LLMProviderFailure in RETRYABLE
    assert issubclass(AllProvidersExhausted, LLMError)


def test_run_chain_with_no_providers_raises(tmp_path):
    with pytest.raises(AllProvidersExhausted):
        LLMClient(http_client=FakeHTTP()).run_chain([], MESSAGES)


# ── cost ceiling (R18) ────────────────────────────────────────────────


def _priced_client(budget_usd, calls: int = 2):
    provider, _ = make_provider(in_price=12.0, out_price=12.0)
    http = FakeHTTP(
        *(
            FakeResponse(
                200,
                {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 500, "completion_tokens": 500},
                },
            )
            for _ in range(calls)
        )
    )
    return LLMClient(http_client=http, budget_usd=budget_usd), provider


def test_budget_is_cumulative_across_calls():
    client, provider = _priced_client(0.015)
    model = provider.default_model
    assert client.complete(provider, model, MESSAGES).cost_usd == pytest.approx(0.012)
    with pytest.raises(BudgetExceeded):
        client.complete(provider, model, MESSAGES)
    assert client.cost_used_usd == pytest.approx(0.024)


def test_set_budget_enforces_a_lower_ceiling():
    client, provider = _priced_client(None, calls=1)
    client.set_budget(0.001)
    with pytest.raises(BudgetExceeded):
        client.complete(provider, provider.default_model, MESSAGES)


# ── envelope (R24) ────────────────────────────────────────────────────


def _dry_run_result(tmp_path):
    provider, model = make_provider()
    client = LLMClient(http_client=FakeHTTP(), tracker=QuotaTracker(cache_dir=tmp_path))
    return client.complete(provider, model, MESSAGES, dry_run=True), provider, model


def test_build_envelope_hash_chains_content_and_metadata(tmp_path):
    result, provider, model = _dry_run_result(tmp_path)
    content = {"score": 87, "categories": {"contact": "ok"}}
    envelope = build_envelope(
        content,
        result,
        run_id="run-1",
        prompt_version="1.0.0",
        schema_version="1",
        idempotency_key="k" * 64,
    )
    assert (
        envelope["artifact_hash"]
        == hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()
    )
    assert envelope["provider"] == provider.id
    assert envelope["model"] == model.id
    assert envelope["run_id"] == "run-1"
    assert envelope["temperature"] == 0.0
    assert envelope["prev_hash"] is None
    body = {k: v for k, v in envelope.items() if k != "envelope_hash"}
    assert (
        envelope["envelope_hash"]
        == hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    )


def test_build_envelope_is_tamper_evident(tmp_path):
    result, _, _ = _dry_run_result(tmp_path)
    kwargs = {
        "run_id": "run-1",
        "prompt_version": "1.0.0",
        "schema_version": "1",
        "idempotency_key": "k" * 64,
    }
    first = build_envelope({"score": 87}, result, **kwargs)
    second = build_envelope({"score": 88}, result, **kwargs)
    assert first["artifact_hash"] != second["artifact_hash"]
    assert first["envelope_hash"] != second["envelope_hash"]


def test_build_envelope_links_to_the_previous_artifact(tmp_path):
    result, _, _ = _dry_run_result(tmp_path)
    prev = "a" * 64
    envelope = build_envelope(
        {"x": 1},
        result,
        prev_hash=prev,
        run_id="run-2",
        prompt_version="1.0.0",
        schema_version="1",
        idempotency_key="k" * 64,
    )
    assert envelope["prev_hash"] == prev
