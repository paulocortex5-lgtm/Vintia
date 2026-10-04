"""Per-domain rate limiting for outbound fetches (task 2.1, §8).

Politeness policy:

* at least ``min_interval_sec`` between two requests to the same domain;
* at most ``max_per_day`` requests per domain per UTC day.

``clock`` and ``sleep`` are injectable so tests run without real delays
(the pattern used by :class:`engine.retry.CircuitBreaker`). The next slot
is reserved under a lock, then slept *outside* it, so concurrent callers
to different domains never block each other while sleeping.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable

from ..errors import RateLimitError

DEFAULT_MIN_INTERVAL_SEC = 1.0
DEFAULT_MAX_PER_DAY = 500
DAY_SEC = 86400


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


class DomainRateLimiter:
    """Gate outbound requests per domain: spacing + daily budget."""

    def __init__(
        self,
        *,
        min_interval_sec: float | None = None,
        max_per_day: int | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval_sec = (
            min_interval_sec
            if min_interval_sec is not None
            else _env_float("VANTIA_FETCH_MIN_INTERVAL_SEC", DEFAULT_MIN_INTERVAL_SEC)
        )
        self.max_per_day = (
            max_per_day
            if max_per_day is not None
            else _env_int("VANTIA_FETCH_MAX_PER_DAY", DEFAULT_MAX_PER_DAY)
        )
        self._clock = clock
        self._sleep = sleep
        self._next_slot: dict[str, float] = {}
        self._usage: dict[str, tuple[int, int]] = {}  # domain -> (utc_day, count)
        self._lock = threading.Lock()

    def acquire(self, domain: str) -> float:
        """Reserve the next request slot for ``domain`` and sleep until it.

        Returns the seconds slept. Raises :class:`RateLimitError` when the
        domain's daily budget is exhausted (callers surface it as a terminal
        failure — hammering a domain that already refused us is impolite).
        """
        with self._lock:
            now = self._clock()
            day = int(now // DAY_SEC)
            used_day, used = self._usage.get(domain, (day, 0))
            if used_day != day:
                used = 0
            if used >= self.max_per_day:
                raise RateLimitError(
                    f"daily fetch budget exhausted for {domain}",
                    domain=domain,
                    used=used,
                    max_per_day=self.max_per_day,
                    resets_at=int((day + 1) * DAY_SEC),
                )
            earliest = self._next_slot.get(domain, 0.0)
            wait = max(0.0, earliest - now)
            self._next_slot[domain] = max(now, earliest) + self.min_interval_sec
            self._usage[domain] = (day, used + 1)
        if wait > 0:
            self._sleep(wait)
        return wait
