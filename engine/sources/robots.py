"""robots.txt handling for outbound fetches (task 2.1, §8).

One robots.txt per origin is fetched (through the rate limiter, never
through the robots gate itself) and cached for ``ttl_sec``.

Policy — the status of ``/robots.txt`` decides how strictly we read it:

* ``200``       → parse and enforce the rules for our user-agent;
* ``401``/``403`` → the site asked visitors to stay out: disallow everything;
* ``404``/``410`` → no rules published: allow everything;
* ``5xx``/``429``/network failure → fail **open** with a warning: a broken
  origin must not silently kill the pipeline — the per-domain rate limiter
  still throttles us, and page-level failures surface as :class:`FetchError`.
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from urllib.robotparser import RobotFileParser

import httpx

LOGGER = logging.getLogger("vantia.sources.robots")

DEFAULT_TTL_SEC = 6 * 3600
#: robots.txt files are tiny; anything bigger is a honeypot or a runaway CMS.
MAX_ROBOTS_LINES = 50_000


@dataclass(frozen=True)
class _Policy:
    checked_at: float
    mode: str  # "allow" | "disallow" | "parse"
    parser: RobotFileParser | None = None


class RobotsCache:
    """Per-origin robots.txt cache with a documented status-code policy."""

    def __init__(
        self,
        getter: Callable[[str], httpx.Response],
        *,
        user_agent: str,
        ttl_sec: float = DEFAULT_TTL_SEC,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._getter = getter
        self.user_agent = user_agent
        self.ttl_sec = ttl_sec
        self._clock = clock
        self._policies: dict[str, _Policy] = {}

    @staticmethod
    def robots_url(url: str) -> str:
        """``https://host/path`` → ``https://host/robots.txt``."""
        parts = urllib.parse.urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}/robots.txt"

    def can_fetch(self, url: str) -> bool:
        """True when ``url`` may be fetched, consulting the cached policy."""
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        now = self._clock()
        policy = self._policies.get(origin)
        if policy is None or now - policy.checked_at >= self.ttl_sec:
            policy = self._refresh(origin)
            self._policies[origin] = policy
        if policy.mode == "allow":
            return True
        if policy.mode == "disallow":
            return False
        assert policy.parser is not None, "parse policy must carry a parser"
        return bool(policy.parser.can_fetch(self.user_agent, url))

    def _refresh(self, origin: str) -> _Policy:
        url = f"{origin}/robots.txt"
        try:
            resp = self._getter(url)
        except Exception as exc:  # noqa: BLE001 — any failure means: fail open
            LOGGER.warning("robots.txt unavailable for %s (%s); failing open", origin, exc)
            return _Policy(self._clock(), "allow")
        status = resp.status_code
        now = self._clock()
        if status == 200:
            parser = RobotFileParser()
            parser.set_url(url)
            parser.parse(resp.text.splitlines()[:MAX_ROBOTS_LINES])
            return _Policy(now, "parse", parser)
        if status in (401, 403):
            LOGGER.warning("robots.txt for %s returned %d; disallowing everything", origin, status)
            return _Policy(now, "disallow")
        if status in (404, 410):
            return _Policy(now, "allow")
        LOGGER.warning("robots.txt for %s returned %d; failing open", origin, status)
        return _Policy(now, "allow")
