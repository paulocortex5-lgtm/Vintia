"""Retry with exponential backoff + jitter, and a circuit breaker (§14, §17).

:func:`retry_with_backoff` covers transient LLM/network failures (429, 5xx,
timeout). :class:`CircuitBreaker` short-circuits repeated failures so one
broken provider cannot burn the whole run.

``sleep`` is injectable so tests run without real delays.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

from .errors import CircuitOpenError, VantiaError

LOGGER = logging.getLogger("vantia.retry")

T = TypeVar("T")

#: Exceptions worth retrying by default.
DEFAULT_RETRYABLE: tuple[type[Exception], ...] = (
    VantiaError,
    TimeoutError,
    ConnectionError,
)


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_sec: float = 2.0,
    cap_sec: float = 60.0,
    retryable: tuple[type[Exception], ...] = DEFAULT_RETRYABLE,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn`` up to ``attempts`` times with exponential backoff + jitter."""
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retryable as exc:
            last = exc
            if attempt >= attempts:
                break
            delay = min(cap_sec, base_sec * (2 ** (attempt - 1)))
            delay += random.uniform(0.0, delay * 0.25)
            LOGGER.warning("retry %d/%d after %.1fs: %s", attempt, attempts, delay, exc)
            sleep(delay)
    assert last is not None, "unreachable: attempts loop must have raised or returned"
    raise last


class CircuitBreaker:
    """Consecutive-failure circuit breaker (§14).

    State machine: closed -> open (after ``failure_threshold`` failures)
    -> half_open (after ``reset_after_sec``) -> closed on success.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_after_sec: float = 300.0,
        name: str = "default",
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_after_sec = reset_after_sec
        self.name = name
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        """Current state; transitions ``open`` -> ``half_open`` on expiry."""
        if self._opened_at is not None:
            if self._clock() - self._opened_at >= self.reset_after_sec:
                self._failures = 0
                self._opened_at = None
                return "half_open"
            return "open"
        return "closed"

    def allow(self) -> bool:
        """Raise :class:`CircuitOpenError` if the breaker is open."""
        if self.state == "open":
            raise CircuitOpenError(f"circuit '{self.name}' is open")
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = self._clock()
