"""End-to-end failover & chaos tests (task 7.2).

Chaos injected offline — provider connection loss, 429/5xx, a Supabase
outage and a mid-run crash — with every HTTP call served by
``httpx.MockTransport`` and every sleep/clock injected. Zero network,
zero real sleeps. Each journey proves the platform degrades *honestly*:
failures surface as their real codes, never as fabricated output.
"""

import json
from pathlib import Path

import httpx
import pytest

from engine.credits.ledger import CreditLedger
from engine.errors import (
    AllProvidersExhausted,
    CircuitOpenError,
    FetchError,
    LLMNetworkError,
)
from engine.idempotency import IdempotencyRegistry
from engine.json_utils import atomic_write_json
from engine.llm.client import LLMClient
from engine.llm.router import LLMModel, LLMProvider
from engine.pipeline import run_ats_scan
from engine.retry import CircuitBreaker
from engine.sources.fetch import Fetcher
from engine.sources.ratelimit import DomainRateLimiter

MSGS = [{"role": "user", "content": "hello"}]

OK_BODY = {
    "id": "gen-chaos",
    "choices": [{"message": {"content": "done"}}],
    "usage": {"prompt_tokens": 5, "completion_tokens": 7},
}

JOB_URL = "https://job-boards.greenhouse.io/vaulttec/jobs/127817"

GREENHOUSE_JOB = {
    "id": 127817,
    "title": "Backend Engineer",
    "updated_at": "2026-09-14T10:55:28-05:00",
    "location": {"name": "London, United Kingdom"},
    "absolute_url": JOB_URL,
    "company_name": "Acme Robotics Ltd",
    "content": (
        "<p>Build Python services in London.</p>"
        "<ul><li>Python</li><li>Kubernetes</li><li>PostgreSQL</li>"
        "<li>5 years experience</li></ul>"
    ),
}

RESUME_MD = """# Ada Okafor
Backend Engineer
Location: London, UK
ada@example.com | +44 20 1234 5678

## Skills
- Python, Kubernetes, PostgreSQL

## Experience
Backend Engineer, Acme (Jan 2021 - Present)
- Shipped the migration; cut p95 latency by 40%
"""


def make_provider(pid: str, host: str):
    model = LLMModel(id=f"{pid}-model")
    provider = LLMProvider(
        id=pid,
        display=pid,
        tier="free",
        base_url=f"https://{host}/v1/chat/completions",
        api_key_env="",
        models=[model],
    )
    return provider, model


def chaos_transport(seen: list[str]):
    """down → ConnectError; limited → 429; broken → 503; api → 200."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        host = request.url.host
        if host == "down.example":
            raise httpx.ConnectError("connection refused", request=request)
        if host == "limited.example":
            return httpx.Response(429, text="rate limited")
        if host == "broken.example":
            return httpx.Response(503, text="upstream exploded")
        return httpx.Response(200, json=OK_BODY)

    return handler


def make_client(seen: list[str]) -> LLMClient:
    return LLMClient(http_client=httpx.Client(transport=httpx.MockTransport(chaos_transport(seen))))


def make_fetcher(handler):
    """Fetcher over ``handler`` with a request log; /robots.txt is 404."""
    seen: list[str] = []

    def combined(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return handler(request)

    limiter = DomainRateLimiter(min_interval_sec=0.0, max_per_day=10**6, sleep=lambda _s: None)
    fetcher = Fetcher(
        client=httpx.Client(transport=httpx.MockTransport(combined)),
        limiter=limiter,
        retries=1,
        sleep=lambda _s: None,
    )
    return fetcher, seen


def write_upload(tmp_path) -> str:
    ws = tmp_path / "ws9"
    ws.mkdir(exist_ok=True)
    path = ws / "cv.md"
    path.write_text(RESUME_MD, encoding="utf-8")
    return str(path)


# ── 1. provider failover: network loss then rate limit ────────────────────


def test_chain_walks_past_network_loss_and_rate_limits():
    """ConnectError → 429 → 200: the third provider serves, hosts pinned."""
    alpha, alpha_m = make_provider("alpha", "down.example")
    beta, beta_m = make_provider("beta", "limited.example")
    gamma, gamma_m = make_provider("gamma", "api.example")
    seen: list[str] = []
    client = make_client(seen)

    result = client.run_chain([(alpha, alpha_m), (beta, beta_m), (gamma, gamma_m)], MSGS)

    assert result.provider == "gamma"
    assert result.text == "done"
    assert result.dry_run is False
    assert set(seen) == {"down.example", "limited.example", "api.example"}


# ── 2. every provider down → honest exhaustion, never fabricated output ───


def test_every_provider_down_raises_honest_exhaustion():
    alpha, alpha_m = make_provider("alpha", "down.example")
    beta, beta_m = make_provider("beta", "limited.example")
    broken, broken_m = make_provider("broken", "broken.example")
    client = make_client([])

    with pytest.raises(AllProvidersExhausted) as excinfo:
        client.run_chain([(alpha, alpha_m), (beta, beta_m), (broken, broken_m)], MSGS)

    attempts = excinfo.value.attempts
    assert len(attempts) == 3
    assert attempts[0].startswith("alpha:")
    assert attempts[1].startswith("beta:")
    assert attempts[2].startswith("broken:")
    # The error carries the attempt trail, not a fake success.
    assert excinfo.value.code == "all_providers_exhausted"


# ── 3. circuit breaker: trips on repeated failure, half-opens, recovers ───


def test_circuit_breaker_trips_and_recovers_without_real_sleep():
    now = {"t": 0.0}
    breaker = CircuitBreaker(
        failure_threshold=2, reset_after_sec=60.0, name="chaos", clock=lambda: now["t"]
    )
    down, down_m = make_provider("down", "down.example")
    healthy, healthy_m = make_provider("healthy", "api.example")
    client = make_client([])

    for _ in range(2):
        breaker.allow()
        with pytest.raises(LLMNetworkError):
            client.complete(down, down_m, MSGS)
        breaker.record_failure()

    with pytest.raises(CircuitOpenError):
        breaker.allow()

    # After the reset window the breaker half-opens; a success closes it.
    now["t"] = 61.0
    assert breaker.state == "half_open"
    result = client.complete(healthy, healthy_m, MSGS)
    breaker.record_success()
    assert breaker.state == "closed"
    assert result.text == "done"


# ── 4. Supabase outage: the local ledger never loses a movement ───────────


def test_supabase_outage_never_loses_a_credit_movement(tmp_path):
    class DownSupabase:
        def upsert(self, table, rows, service=True):
            raise ConnectionError("supabase unreachable")

        def query(self, table, filters, select="*", *, service=False):
            raise ConnectionError("supabase unreachable")

    path = tmp_path / "ledger.json"
    ledger = CreditLedger(store_path=str(path), supabase_client=DownSupabase())

    ledger.topup("u-chaos", 5_000, ref="pack-chaos")
    ledger.spend("u-chaos", 2_000, ref="cv_scan:chaos")
    assert ledger.balance("u-chaos") == 3_000  # mirror down, movement intact

    # Durability: a fresh ledger over the same file still sees the truth.
    reopened = CreditLedger(store_path=str(path))
    assert reopened.balance("u-chaos") == 3_000
    assert [e["ref"] for e in reopened.entries("u-chaos")] == ["pack-chaos", "cv_scan:chaos"]


# ── 5. mid-run crash → deterministic replay + tamper-evident registry ─────


def test_mid_run_crash_recovers_and_replay_is_deterministic(tmp_path):
    write_upload(tmp_path)
    registry = IdempotencyRegistry(path=str(tmp_path / "registry.json"))

    # Attempt 1: the job board is down mid-run — the pipeline fails loudly.
    def board_down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("board down", request=request)

    down_fetcher, _ = make_fetcher(board_down)
    with pytest.raises(FetchError):
        run_ats_scan(
            "ws9",
            "cv.md",
            JOB_URL,
            fetcher=down_fetcher,
            store_dir=str(tmp_path),
            run_id="run-chaos",
        )

    # Attempt 2: network restored — same inputs produce the real report.
    def healthy_handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "boards-api.greenhouse.io":
            return httpx.Response(200, json=GREENHOUSE_JOB)
        return httpx.Response(404)

    fetcher, _ = make_fetcher(healthy_handler)
    first = run_ats_scan(
        "ws9",
        "cv.md",
        JOB_URL,
        fetcher=fetcher,
        store_dir=str(tmp_path),
        run_id="run-chaos",
    )["report"]

    # Deterministic replay: identical inputs → identical artifact.
    replay = run_ats_scan(
        "ws9",
        "cv.md",
        JOB_URL,
        fetcher=fetcher,
        store_dir=str(tmp_path),
        run_id="run-chaos",
    )["report"]
    assert replay == first

    # Registry: completed work is recorded once, verified, and tamper-evident.
    digest = registry.record_complete("9.5|chaos|ws9/cv.md", ["ws9/cv.md.ats.json"])
    assert registry.is_complete("9.5|chaos|ws9/cv.md")
    ok, bad = registry.verify()
    assert ok and bad == []

    data = json.loads(Path(registry.path).read_text(encoding="utf-8"))
    data[digest]["artifacts"].append("evil.json")
    atomic_write_json(registry.path, data)
    ok, bad = registry.verify()
    assert not ok
    assert "9.5|chaos|ws9/cv.md" in bad


if __name__ == "__main__":  # pragma: no cover — direct-run convenience
    pytest.main([__file__, "-v"])
