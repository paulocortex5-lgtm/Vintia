"""Unified LLM client — every call in the engine goes through here (R26).

Deliverable of task 1.7 (master prompt v4.0).

Responsibilities
  * translate a conversation into the payload style of any registered
    provider (openai / gemini / anthropic / cohere) and back-parse the
    response into one normalized :class:`LLMResult`
  * enforce temperature 0 for schema-bound work (R16), a 120s per-call
    timeout (R17) and the run cost ceiling (R18)
  * dry-run support: with ``VANTIA_DRY_RUN=1`` no network is touched and
    a deterministic stub is returned (R25)
  * after every success: cost ledger entry + quota increment (R28)
  * raise :class:`~engine.errors.AllProvidersExhausted` when an entire
    chain fails (R35) — the task stays in_progress, not failed

Generators call :meth:`LLMClient.run_chain` with a chain produced by
:func:`engine.llm.router.pick`; they never build HTTP requests themselves.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..errors import (
    AllProvidersExhausted,
    BudgetExceeded,
    LLMEmptyResponseError,
    LLMNetworkError,
    LLMProviderFailure,
    LLMTimeoutError,
)
from .router import LLMModel, LLMProvider

# R17 — per-call timeout (seconds).
DEFAULT_TIMEOUT_SEC = 120.0

# R25 — dry-run stub; deterministic, zero cost, no network.
DRY_RUN_STUB = '{"dry_run": true, "note": "VANTIA_DRY_RUN=1; no LLM call was made"}'

# R24 — every artifact envelope records these fields.
ENVELOPE_FIELDS = (
    "provider",
    "model",
    "prompt_version",
    "schema_version",
    "temperature",
    "idempotency_key",
    "run_id",
    "artifact_hash",
    "prev_hash",
)

#: Transient provider faults that justify moving to the next provider.
RETRYABLE: tuple[type[Exception], ...] = (
    LLMNetworkError,
    LLMTimeoutError,
    LLMProviderFailure,
    LLMEmptyResponseError,
)


@dataclass(frozen=True)
class LLMResult:
    """Normalized result of one provider call."""

    text: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    response_id: str | None = None
    dry_run: bool = False
    raw: dict[str, Any] | None = field(default=None, compare=False)

    @property
    def usd(self) -> float:
        return self.cost_usd


def is_dry_run(dry_run: bool | None = None) -> bool:
    """R25: honour an explicit flag, else the VANTIA_DRY_RUN env var."""
    if dry_run is not None:
        return bool(dry_run)
    return os.environ.get("VANTIA_DRY_RUN") == "1"


def _estimate_tokens(text: str) -> int:
    """Token estimate (~4 chars/token) when tiktoken is unavailable."""
    try:
        import tiktoken  # type: ignore[import-untyped]

        enc = tiktoken.get_encoding("cl100k_base")
        return max(1, len(enc.encode(text)))
    except Exception:  # noqa: BLE001 — estimation must never break a call
        return max(1, len(text) // 4)


def _to_openai_messages(messages: list[dict[str, Any]], system: str | None) -> list[dict[str, str]]:
    """Normalize the engine's message shape to a plain role/content list."""
    out: list[dict[str, str]] = []
    if system:
        out.append({"role": "system", "content": system})
    for msg in messages:
        role = str(msg.get("role", "user"))
        content = msg.get("content")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = str(content)
        out.append({"role": role, "content": content})
    return out


def build_payload(
    provider: LLMProvider,
    model: LLMModel,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    system: str | None = None,
) -> dict[str, Any]:
    """Build the request body for a provider's payload style."""
    cap = int(max_tokens if max_tokens is not None else model.max_tokens)
    norm = _to_openai_messages(messages, system)
    if provider.payload_style == "openai":
        return {"model": model.id, "messages": norm, "temperature": temperature, "max_tokens": cap}
    if provider.payload_style == "anthropic":
        system_msgs = [m["content"] for m in norm if m["role"] == "system"]
        body: dict[str, Any] = {"model": model.id, "max_tokens": cap, "temperature": temperature}
        if system_msgs:
            body["system"] = "\n".join(system_msgs)
        body["messages"] = [m for m in norm if m["role"] != "system"]
        return body
    if provider.payload_style == "cohere":
        system_msgs = [m["content"] for m in norm if m["role"] == "system"]
        body = {"model": model.id, "temperature": temperature, "max_tokens": cap}
        if system_msgs:
            body["system"] = "\n".join(system_msgs)
        body["messages"] = [m for m in norm if m["role"] != "system"]
        return body
    # gemini / vertex
    system_msgs = [m["content"] for m in norm if m["role"] == "system"]
    contents: list[dict[str, Any]] = []
    if system_msgs:
        contents.append({"role": "user", "parts": [{"text": "\n".join(system_msgs)}]})
    for msg in norm:
        if msg["role"] == "system":
            continue
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    return {
        "contents": contents,
        "generationConfig": {"temperature": temperature, "maxOutputTokens": cap},
    }


def extract_result(provider: LLMProvider, response: dict[str, Any]) -> tuple[str, dict[str, int]]:
    """Pull text + token usage out of any payload-style response."""
    usage: dict[str, int] = {}
    text = ""
    style = provider.payload_style
    if style == "openai":
        choices = response.get("choices") or [{}]
        text = str(choices[0].get("message", {}).get("content") or "")
        raw_usage = response.get("usage") or {}
        usage = {"tokens_in": int(raw_usage.get("prompt_tokens") or 0)}
        usage["tokens_out"] = int(raw_usage.get("completion_tokens") or 0)
    elif style == "cohere":
        text = "".join(
            str(part.get("text", "")) for part in (response.get("message", {}).get("content") or [])
        )
        raw_usage = response.get("usage") or {}
        usage = {
            "tokens_in": int(raw_usage.get("input_tokens") or 0),
            "tokens_out": int(raw_usage.get("output_tokens") or 0),
        }
    elif style == "anthropic":
        text = "".join(str(part.get("text", "")) for part in (response.get("content") or []))
        raw_usage = response.get("usage") or {}
        usage = {
            "tokens_in": int(raw_usage.get("input_tokens") or 0),
            "tokens_out": int(raw_usage.get("output_tokens") or 0),
        }
    else:  # gemini / vertex
        candidates = response.get("candidates") or [{}]
        parts = ((candidates[0].get("content") or {}).get("parts")) or []
        text = "".join(str(part.get("text", "")) for part in parts)
        raw_usage = response.get("usageMetadata") or {}
        usage = {
            "tokens_in": int(raw_usage.get("promptTokenCount") or 0),
            "tokens_out": int(raw_usage.get("candidatesTokenCount") or 0),
        }
    return text, usage


class LLMClient:
    """Execute one provider call; :meth:`run_chain` walks a failover chain."""

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        budget_usd: float | None = None,
        tracker: Any | None = None,
    ) -> None:
        self._http = http_client
        self._budget = budget_usd
        self._tracker = tracker
        self.cost_used_usd = 0.0

    @property
    def http(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=DEFAULT_TIMEOUT_SEC)
        return self._http

    def set_budget(self, budget_usd: float) -> None:
        self._budget = budget_usd

    # ── Single provider call ──────────────────────────────────────────
    def complete(
        self,
        provider: LLMProvider,
        model: LLMModel,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        dry_run: bool | None = None,
        run_id: str | None = None,
    ) -> LLMResult:
        """Call one provider. Raises a retryable LLM error on failure.

        On success the result is cost-capped (R18) and the quota tracker
        is incremented (R28).
        """
        if is_dry_run(dry_run):
            return LLMResult(
                text=DRY_RUN_STUB,
                provider=provider.id,
                model=model.id,
                tokens_in=_estimate_tokens(system or "")
                + sum(_estimate_tokens(str(m.get("content", ""))) for m in messages),
                tokens_out=0,
                cost_usd=0.0,
                dry_run=True,
            )
        payload = build_payload(
            provider, model, messages, temperature=temperature, max_tokens=max_tokens, system=system
        )
        headers = provider.build_headers(model)
        try:
            response = self.http.post(
                provider.resolve_url(model), headers=headers, json=payload, timeout=timeout_sec
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"{provider.id}: timed out after {timeout_sec}s") from exc
        except httpx.HTTPError as exc:
            raise LLMNetworkError(f"{provider.id}: {exc}") from exc

        if response.status_code == 401:
            raise LLMProviderFailure(f"{provider.id}: 401 — key invalid (skip to next provider)")
        if response.status_code == 429:
            raise LLMProviderFailure(
                f"{provider.id}: 429 — rate limit / quota (skip to next provider)"
            )
        if response.status_code >= 500:
            raise LLMProviderFailure(
                f"{provider.id}: HTTP {response.status_code} — {response.text[:200]}"
            )
        if response.status_code == 400:
            # Bad request is not worth failing over for; surface it.
            raise LLMProviderFailure(f"{provider.id}: HTTP 400 — {response.text[:300]}")

        data = response.json()
        text, usage = extract_result(provider, data)
        tokens_in = int(
            usage.get("tokens_in")
            or _estimate_tokens(system or "")
            + sum(_estimate_tokens(str(m.get("content", ""))) for m in messages)
        )
        tokens_out = int(usage.get("tokens_out") or _estimate_tokens(text))
        cost = (
            model.in_usd_per_mtok * tokens_in + model.out_usd_per_mtok * tokens_out
        ) / 1_000_000.0
        if not text.strip():
            raise LLMEmptyResponseError(
                f"{provider.id}: HTTP {response.status_code} but empty content"
            )
        self._account(provider, tokens_in, tokens_out, cost, run_id=run_id)
        return LLMResult(
            text=text,
            provider=provider.id,
            model=model.id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            response_id=data.get("id"),
            raw=data,
        )

    def _account(
        self,
        provider: LLMProvider,
        tokens_in: int,
        tokens_out: int,
        cost: float,
        run_id: str | None,
    ) -> None:
        """R18 cost ceiling + R28 quota/cost ledger bookkeeping."""
        self.cost_used_usd += cost
        if self._budget is not None and self.cost_used_usd > self._budget + 1e-12:
            raise BudgetExceeded(used_usd=self.cost_used_usd, budget_usd=self._budget)
        if self._tracker is not None:
            self._tracker.increment_usage(
                provider.id, tokens_in, tokens_out, model=provider.default_model, run_id=run_id
            )

    # ── Failover chain ────────────────────────────────────────────────
    def run_chain(
        self,
        chain: list[tuple[LLMProvider, LLMModel]],
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        dry_run: bool | None = None,
        run_id: str | None = None,
    ) -> LLMResult:
        """Try each (provider, model) in order; first success wins (R35).

        Every failure is collected; when nothing works, raise
        :class:`AllProvidersExhausted` carrying the attempt list.
        """
        attempts: list[str] = []
        last_error: Exception | None = None
        for provider, model in chain:
            try:
                return self.complete(
                    provider,
                    model,
                    messages,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_sec=timeout_sec,
                    dry_run=dry_run,
                    run_id=run_id,
                )
            except RETRYABLE as exc:
                attempts.append(f"{provider.id}:{model.id} → {exc}")
                last_error = exc
                continue
        raise AllProvidersExhausted(
            f"all {len(chain)} provider(s) failed; last: {last_error}", attempts=attempts
        ) from last_error


# ── Artifact envelope (R24) ──────────────────────────────────────────────
def build_envelope(
    content: Any,
    result: LLMResult,
    *,
    run_id: str,
    prompt_version: str,
    schema_version: str,
    idempotency_key: str,
    prev_hash: str | None = None,
) -> dict[str, Any]:
    """Wrap LLM-generated content in the hash-chained envelope (R24).

    ``artifact_hash = sha256(canonical_json(content))`` chained with
    ``prev_hash`` so the run log is tamper-evident.
    """
    from ..json_utils import canonical_json

    content_hash = hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()
    envelope: dict[str, Any] = {
        "provider": result.provider,
        "model": result.model,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "temperature": 0.0,
        "idempotency_key": idempotency_key,
        "run_id": run_id,
        "artifact_hash": content_hash,
        "prev_hash": prev_hash,
        "content": content,
    }
    envelope["envelope_hash"] = hashlib.sha256(
        canonical_json({k: v for k, v in envelope.items() if k != "envelope_hash"}).encode("utf-8")
    ).hexdigest()
    return envelope
