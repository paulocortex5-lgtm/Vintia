"""Source-fetch tests: rate limiter, robots.txt policy, fetch pipeline (task 2.1).

Every HTTP exchange goes through ``httpx.MockTransport`` — zero network I/O.
Clock and sleep are faked so no test ever waits in real time.
"""

import json

import httpx
import pytest

from engine.errors import FetchError, RateLimitError, RobotsDisallowed, TransientFetchError
from engine.sources import DomainRateLimiter, Fetcher, RobotsCache

ROBOTS_BLOCK_PRIVATE = "User-agent: *\nDisallow: /private\n"


class FakeClock:
    """Wall clock whose ``sleep`` advances time and records the wait."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def build(handler, *, retries: int = 3, max_bytes: int | None = None, limiter=None):
    """Fetcher wired to ``handler``; returns (fetcher, backoff_sleeps)."""
    sleeps: list[float] = []
    fetcher = Fetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        limiter=limiter
        or DomainRateLimiter(
            min_interval_sec=0.0, max_per_day=10**6, clock=FakeClock(), sleep=lambda _s: None
        ),
        retries=retries,
        max_bytes=max_bytes,
        sleep=sleeps.append,
    )
    return fetcher, sleeps


# ── rate limiter ──────────────────────────────────────────────────────


def test_rate_limiter_spaces_requests_per_domain():
    clk = FakeClock()
    lim = DomainRateLimiter(min_interval_sec=2.0, max_per_day=100, clock=clk, sleep=clk.sleep)
    assert lim.acquire("a.example") == 0.0
    assert lim.acquire("a.example") == pytest.approx(2.0)
    assert lim.acquire("a.example") == pytest.approx(2.0)
    # a different domain is not throttled by a.example's schedule
    assert lim.acquire("b.example") == 0.0
    assert clk.sleeps == [2.0, 2.0]


def test_rate_limiter_daily_budget_and_rollover():
    clk = FakeClock(start=100.0)
    lim = DomainRateLimiter(min_interval_sec=0.0, max_per_day=2, clock=clk, sleep=clk.sleep)
    lim.acquire("a.example")
    lim.acquire("a.example")
    with pytest.raises(RateLimitError) as excinfo:
        lim.acquire("a.example")
    assert excinfo.value.code == "rate_limited"
    assert excinfo.value.context["domain"] == "a.example"
    assert excinfo.value.context["used"] == 2
    clk.now += 86_400  # next UTC day: budget resets
    assert lim.acquire("a.example") == 0.0


# ── robots.txt ────────────────────────────────────────────────────────


def test_robots_rules_enforced_and_cached_per_origin():
    robots_calls: list[str] = []
    page_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            robots_calls.append(str(request.url))
            return httpx.Response(200, text=ROBOTS_BLOCK_PRIVATE)
        page_calls.append(str(request.url))
        return httpx.Response(200, text="body")

    fetcher, _ = build(handler, retries=1)
    with pytest.raises(RobotsDisallowed) as excinfo:
        fetcher.fetch("https://jobs.example/private/42")
    assert excinfo.value.code == "robots_disallowed"
    assert excinfo.value.context["robots_txt"] == "https://jobs.example/robots.txt"
    assert page_calls == [], "robots gate must fire before any page request"

    assert fetcher.fetch("https://jobs.example/open/1").status_code == 200
    assert fetcher.fetch("https://jobs.example/open/2").status_code == 200
    assert len(robots_calls) == 1, "robots.txt must be fetched once per origin"


def test_robots_missing_404_allows_everything():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404 if request.url.path == "/robots.txt" else 200, text="page")

    fetcher, _ = build(handler, retries=1)
    assert fetcher.can_fetch("https://jobs.example/anything")
    assert fetcher.fetch("https://jobs.example/anything").status_code == 200


def test_robots_403_disallows_everything():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403 if request.url.path == "/robots.txt" else 200, text="no")

    fetcher, _ = build(handler, retries=1)
    assert not fetcher.can_fetch("https://jobs.example/anything")
    with pytest.raises(RobotsDisallowed):
        fetcher.fetch("https://jobs.example/anything")


def test_robots_network_failure_fails_open():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            raise httpx.ConnectError("refused")
        return httpx.Response(200, text="page")

    fetcher, _ = build(handler, retries=1)
    assert fetcher.fetch("https://jobs.example/listing/1").status_code == 200


def test_robots_cache_honours_ttl():
    calls: list[str] = []
    clk = FakeClock()

    def getter(url: str) -> httpx.Response:
        calls.append(url)
        return httpx.Response(200, text="User-agent: *\nDisallow: /admin\n")

    cache = RobotsCache(getter, user_agent="Vantia/test", ttl_sec=100.0, clock=clk)
    assert not cache.can_fetch("https://x.example/admin/dashboard")
    assert len(calls) == 1
    clk.now += 100.0  # TTL expired: re-fetch on next check
    assert not cache.can_fetch("https://x.example/admin/dashboard")
    assert len(calls) == 2


# ── fetch pipeline ────────────────────────────────────────────────────


def test_fetch_success_records_provenance_and_headers():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        seen["ua"] = request.headers.get("user-agent", "")
        seen["query"] = request.url.query.decode()
        return httpx.Response(
            200, text="<html>ok</html>", headers={"content-type": "text/html; charset=utf-8"}
        )

    fetcher, _ = build(handler, retries=1)
    result = fetcher.fetch("https://jobs.example/listing/1", params={"page": "2"})
    assert result.status_code == 200
    assert result.content == "<html>ok</html>"
    assert result.content_type == "text/html"
    assert result.url.startswith("https://jobs.example/listing/1")
    assert result.final_url.startswith(result.url)
    assert "page=2" in result.final_url
    assert result.fetched_at.endswith("Z") and "T" in result.fetched_at
    assert result.elapsed_ms >= 0
    assert seen["ua"].startswith("Vantia/")
    assert seen["query"] == "page=2"


def test_fetch_404_is_terminal_with_status_context():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls.append(1)
        return httpx.Response(404, text="gone")

    fetcher, sleeps = build(handler, retries=3)
    with pytest.raises(FetchError) as excinfo:
        fetcher.fetch("https://jobs.example/missing")
    assert excinfo.value.code == "fetch_error"
    assert excinfo.value.context["status"] == 404
    assert len(calls) == 1, "4xx must not be retried"
    assert sleeps == []


def test_5xx_retries_with_backoff_until_success():
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        pages.append(1)
        if len(pages) < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, text="ok")

    fetcher, sleeps = build(handler, retries=3)
    assert fetcher.fetch("https://jobs.example/flaky").content == "ok"
    assert len(pages) == 3
    assert len(sleeps) == 2
    assert 1.0 <= sleeps[0] <= 1.3, "exponential backoff, attempt 1"
    assert 2.0 <= sleeps[1] <= 2.6, "exponential backoff, attempt 2"


def test_5xx_exhausting_retries_raises_transient_fetch_error():
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        pages.append(1)
        return httpx.Response(500, text="boom")

    fetcher, _ = build(handler, retries=2)
    with pytest.raises(TransientFetchError) as excinfo:
        fetcher.fetch("https://jobs.example/down")
    assert excinfo.value.code == "fetch_transient"
    assert isinstance(excinfo.value, FetchError)
    assert excinfo.value.context["status"] == 500
    assert len(pages) == 2


def test_upstream_429_is_terminal_and_carries_retry_after():
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        pages.append(1)
        return httpx.Response(429, text="slow down", headers={"Retry-After": "7"})

    fetcher, sleeps = build(handler, retries=3)
    with pytest.raises(RateLimitError) as excinfo:
        fetcher.fetch("https://jobs.example/busy")
    assert excinfo.value.context["retry_after"] == 7
    assert len(pages) == 1, "429 must not be retried"
    assert sleeps == []


def test_local_daily_budget_surfaces_rate_limit_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404 if request.url.path == "/robots.txt" else 200, text="x")

    # Budget of one request: the robots.txt fetch consumes it, so the
    # page request hits the local cap without touching the wire again.
    limiter = DomainRateLimiter(
        min_interval_sec=0.0, max_per_day=1, clock=FakeClock(), sleep=lambda _s: None
    )
    fetcher, _ = build(handler, retries=1, limiter=limiter)
    with pytest.raises(RateLimitError) as excinfo:
        fetcher.fetch("https://jobs.example/listing/1")
    assert excinfo.value.context["max_per_day"] == 1


def test_rate_limiter_consulted_before_every_retry():
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        pages.append(1)
        if len(pages) < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, text="ok")

    class SpyLimiter(DomainRateLimiter):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)  # type: ignore[arg-type]
            self.calls: list[str] = []

        def acquire(self, domain: str) -> float:
            self.calls.append(domain)
            return super().acquire(domain)

    limiter = SpyLimiter(
        min_interval_sec=0.0, max_per_day=10**6, clock=FakeClock(), sleep=lambda _s: None
    )
    fetcher, _ = build(handler, retries=3, limiter=limiter)
    assert fetcher.fetch("https://jobs.example/flaky").status_code == 200
    # 1 robots.txt request + 3 page attempts, every one rate-limited
    assert len(limiter.calls) == 4
    assert set(limiter.calls) == {"jobs.example"}


def test_non_http_scheme_refused_before_any_io():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, text="x")

    fetcher, _ = build(handler, retries=1)
    with pytest.raises(FetchError):
        fetcher.fetch("file:///etc/passwd")
    assert calls == []


def test_oversized_body_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="x" * 5000)

    fetcher, _ = build(handler, retries=1, max_bytes=1000)
    with pytest.raises(FetchError) as excinfo:
        fetcher.fetch("https://jobs.example/huge")
    assert excinfo.value.context["max_bytes"] == 1000
    assert excinfo.value.context["content_length"] >= 1000


def test_timeout_is_retried_then_reported():
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        pages.append(1)
        raise httpx.ReadTimeout("too slow")

    fetcher, sleeps = build(handler, retries=2)
    with pytest.raises(TransientFetchError):
        fetcher.fetch("https://jobs.example/slow")
    assert len(pages) == 2
    assert len(sleeps) == 1


def test_close_leaves_injected_client_open_and_closes_owned():
    injected = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(200)))
    fetcher, _ = build(lambda _r: httpx.Response(404))
    fetcher.close()
    assert not injected.is_closed  # never owned, only held by the test
    injected.close()
    owned = Fetcher()
    owned.close()
    assert owned._client is None


def test_post_sends_json_through_the_same_pipeline():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        seen["method"] = request.method
        seen["body"] = request.content
        return httpx.Response(
            200, text='{"ok": true}', headers={"content-type": "application/json"}
        )

    fetcher, _ = build(handler, retries=1)
    result = fetcher.post("https://jobs.example/wday/cxs/acme/site/jobs", json={"limit": 20})
    assert result.status_code == 200
    assert seen["method"] == "POST"
    assert json.loads(seen["body"]) == {"limit": 20}  # type: ignore[arg-type]
    assert result.content == '{"ok": true}'


def test_post_is_gated_by_robots_too():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        calls.append(1)
        return httpx.Response(200, text="{}")

    fetcher, _ = build(handler, retries=1)
    with pytest.raises(RobotsDisallowed):
        fetcher.post("https://jobs.example/private/jobs", json={})
    assert calls == []


def test_post_5xx_is_retried_like_get():
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        pages.append(1)
        return (
            httpx.Response(503, text="busy") if len(pages) < 2 else httpx.Response(200, text="{}")
        )

    fetcher, sleeps = build(handler, retries=2)
    assert fetcher.post("https://jobs.example/api", json={}).status_code == 200
    assert len(pages) == 2
    assert len(sleeps) == 1
