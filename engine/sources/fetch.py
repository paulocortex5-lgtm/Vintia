"""HTTP fetch base — every job/scholarship source goes through here (task 2.1, §8).

Request pipeline:

1. scheme allow-list (``http``/``https`` only);
2. robots.txt gate (:class:`~engine.sources.robots.RobotsCache`);
3. per-domain rate limiter (:class:`~engine.sources.ratelimit.DomainRateLimiter`)
   — consulted before **every** attempt, including retries;
4. GET with retry + exponential backoff on 5xx / timeouts / network errors
   (:class:`TransientFetchError` via :func:`engine.retry.retry_with_backoff`);
   4xx and 429 are terminal (:class:`FetchError` / :class:`RateLimitError`);
5. size cap — bodies above ``max_bytes`` are refused.

All network I/O runs through an injectable ``httpx.Client``, so tests use
``httpx.MockTransport`` and never touch the network.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Self
from urllib.parse import urlsplit

import httpx

from ..errors import FetchError, RateLimitError, RobotsDisallowed, TransientFetchError
from ..logging_config import utc_now
from ..retry import retry_with_backoff
from .ratelimit import DomainRateLimiter
from .robots import RobotsCache

LOGGER = logging.getLogger("vantia.sources.fetch")

DEFAULT_USER_AGENT = "Vantia/0.6 (+https://vantia.ai/bot)"
DEFAULT_TIMEOUT_SEC = 20.0
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_BASE_SEC = 1.0


def _env(name: str, default: str) -> str:
    return os.environ.get(name, "").strip() or default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class FetchResult:
    """Successful fetch: body plus enough provenance to audit it."""

    url: str  # as requested
    final_url: str  # after redirects
    status_code: int
    content: str
    content_type: str
    fetched_at: str  # YYYY-MM-DDTHH:MM:SSZ
    elapsed_ms: int


class Fetcher:
    """Robots-aware, rate-limited HTTP GET with bounded retries."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        limiter: DomainRateLimiter | None = None,
        robots: RobotsCache | None = None,
        user_agent: str | None = None,
        timeout_sec: float | None = None,
        max_bytes: int | None = None,
        retries: int | None = None,
        backoff_base_sec: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.user_agent = user_agent or _env("VANTIA_FETCH_USER_AGENT", DEFAULT_USER_AGENT)
        self.timeout_sec = (
            timeout_sec
            if timeout_sec is not None
            else _env_float("VANTIA_FETCH_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC)
        )
        self.max_bytes = (
            max_bytes
            if max_bytes is not None
            else _env_int("VANTIA_FETCH_MAX_BYTES", DEFAULT_MAX_BYTES)
        )
        self.retries = (
            retries if retries is not None else _env_int("VANTIA_FETCH_RETRIES", DEFAULT_RETRIES)
        )
        self.backoff_base_sec = (
            backoff_base_sec if backoff_base_sec is not None else DEFAULT_BACKOFF_BASE_SEC
        )
        self._sleep = sleep
        self._client = client
        self._owns_client = client is None
        self.limiter = limiter if limiter is not None else DomainRateLimiter(sleep=sleep)
        self.robots = (
            robots
            if robots is not None
            else RobotsCache(self._robots_get, user_agent=self.user_agent)
        )

    # ── lifecycle ──────────────────────────────────────────────────────
    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True,
                timeout=self.timeout_sec,
                headers=self._headers(),
            )
        return self._client

    def close(self) -> None:
        """Close the owned client (an injected client stays open)."""
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en",
        }
        if extra:
            headers.update(extra)
        return headers

    # ── robots.txt (fetched through the limiter, never through the gate) ──
    def _robots_get(self, url: str) -> httpx.Response:
        domain = urlsplit(url).netloc
        self.limiter.acquire(domain)
        try:
            return self._http().get(url, headers=self._headers(), timeout=self.timeout_sec)
        except httpx.HTTPError as exc:
            raise FetchError(f"robots.txt fetch failed: {url}", url=url) from exc

    # ── public API ─────────────────────────────────────────────────────
    def can_fetch(self, url: str) -> bool:
        """robots.txt verdict for ``url`` (cached per origin)."""
        return self.robots.can_fetch(url)

    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> FetchResult:
        """Fetch ``url`` or raise a :class:`FetchError` subclass.

        Raises :class:`RobotsDisallowed` before any network I/O, and
        :class:`RateLimitError` when the local daily budget or an upstream
        429 stops us.
        """
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise FetchError(f"unsupported URL (http/https only): {url}", url=url)
        if not self.robots.can_fetch(url):
            raise RobotsDisallowed(
                f"robots.txt forbids {url}",
                url=url,
                robots_txt=RobotsCache.robots_url(url),
            )
        return retry_with_backoff(
            lambda: self._attempt(url, params=params, headers=headers),
            attempts=max(1, self.retries),
            base_sec=self.backoff_base_sec,
            retryable=(TransientFetchError,),
            sleep=self._sleep,
        )

    def _attempt(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
    ) -> FetchResult:
        domain = urlsplit(url).netloc
        self.limiter.acquire(domain)  # every attempt, retries included
        started = time.monotonic()
        try:
            resp = self._http().get(
                url,
                params=dict(params) if params else None,
                headers=self._headers(headers),
                timeout=self.timeout_sec,
            )
        except httpx.TimeoutException as exc:
            raise TransientFetchError(f"timeout fetching {url}", url=url) from exc
        except httpx.HTTPError as exc:
            raise TransientFetchError(f"network error fetching {url}: {exc}", url=url) from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)

        status = resp.status_code
        if status == 429:
            raise RateLimitError(f"429 from {url}", url=url, retry_after=_retry_after(resp))
        if status >= 500:
            raise TransientFetchError(f"{status} from {url}", url=url, status=status)
        if status >= 400:
            raise FetchError(f"{status} from {url}", url=url, status=status)

        body = resp.content
        declared = resp.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > self.max_bytes:
            raise FetchError(
                f"body too large ({declared} bytes) from {url}",
                url=url,
                max_bytes=self.max_bytes,
                content_length=int(declared),
            )
        if len(body) > self.max_bytes:
            raise FetchError(
                f"body too large ({len(body)} bytes) from {url}",
                url=url,
                max_bytes=self.max_bytes,
                content_length=len(body),
            )

        content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        result = FetchResult(
            url=url,
            final_url=str(resp.url),
            status_code=status,
            content=resp.text,
            content_type=content_type,
            fetched_at=utc_now(),
            elapsed_ms=elapsed_ms,
        )
        LOGGER.debug("fetched %s -> %d in %dms", url, status, elapsed_ms)
        return result


def _retry_after(resp: httpx.Response) -> int | None:
    raw = resp.headers.get("retry-after", "")
    return int(raw) if raw.strip().isdigit() else None
