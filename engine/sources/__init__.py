"""Source adapters — fetching, robots.txt, rate limiting, portals (Phase 2)."""

from .fetch import DEFAULT_USER_AGENT, Fetcher, FetchResult
from .portals import JobListing, PortalAdapter, adapter_for_url, adapters_for, load_listing
from .ratelimit import DomainRateLimiter
from .robots import RobotsCache

__all__ = [
    "DEFAULT_USER_AGENT",
    "DomainRateLimiter",
    "FetchResult",
    "Fetcher",
    "JobListing",
    "PortalAdapter",
    "RobotsCache",
    "adapter_for_url",
    "adapters_for",
    "load_listing",
]
