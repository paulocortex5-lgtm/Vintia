"""Source adapters — fetching, robots, rate limits, portals, government
job sites, sponsor registers and the European search database (Phase 2)."""

from .countries import BY_ISO, EUROPE, CountryTarget, search_targets
from .fetch import DEFAULT_USER_AGENT, Fetcher, FetchResult
from .government import FederalEmploymentAgency
from .portals import (
    JobListing,
    PortalAdapter,
    adapter_for_url,
    adapters_for,
    filter_active,
    load_listing,
)
from .ratelimit import DomainRateLimiter
from .registers import (
    SponsorRegister,
    badge,
    fetch_au_register,
    fetch_uk_register,
    normalize_employer,
)
from .robots import RobotsCache

__all__ = [
    "BY_ISO",
    "DEFAULT_USER_AGENT",
    "EUROPE",
    "CountryTarget",
    "DomainRateLimiter",
    "FederalEmploymentAgency",
    "FetchResult",
    "Fetcher",
    "JobListing",
    "PortalAdapter",
    "RobotsCache",
    "SponsorRegister",
    "adapter_for_url",
    "adapters_for",
    "badge",
    "fetch_au_register",
    "fetch_uk_register",
    "filter_active",
    "load_listing",
    "normalize_employer",
    "search_targets",
]
