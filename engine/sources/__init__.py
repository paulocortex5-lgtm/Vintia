"""Source adapters — fetching, robots.txt, rate limiting (Phase 2, task 2.1)."""

from .fetch import DEFAULT_USER_AGENT, Fetcher, FetchResult
from .ratelimit import DomainRateLimiter
from .robots import RobotsCache

__all__ = [
    "DEFAULT_USER_AGENT",
    "DomainRateLimiter",
    "FetchResult",
    "Fetcher",
    "RobotsCache",
]
