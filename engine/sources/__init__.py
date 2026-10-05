"""Source adapters — fetching, robots, rate limits, portals, government
job sites, sponsor registers and the European search database (Phase 2)."""

from .countries import (
    BY_ISO,
    EUROPE,
    REGISTER_NONE,
    REGISTER_PENDING,
    REGISTER_PUBLISHED,
    CountryTarget,
    europe_iso2,
    search_targets,
)
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
    RegisterSpec,
    SponsorRegister,
    badge,
    empty_register,
    fetch_au_register,
    fetch_register,
    fetch_registers,
    fetch_uk_register,
    normalize_employer,
    register_spec,
)
from .robots import RobotsCache

__all__ = [
    "BY_ISO",
    "DEFAULT_USER_AGENT",
    "EUROPE",
    "REGISTER_NONE",
    "REGISTER_PENDING",
    "REGISTER_PUBLISHED",
    "CountryTarget",
    "DomainRateLimiter",
    "FederalEmploymentAgency",
    "FetchResult",
    "Fetcher",
    "JobListing",
    "PortalAdapter",
    "RegisterSpec",
    "RobotsCache",
    "SponsorRegister",
    "adapter_for_url",
    "adapters_for",
    "badge",
    "empty_register",
    "europe_iso2",
    "fetch_au_register",
    "fetch_register",
    "fetch_registers",
    "fetch_uk_register",
    "filter_active",
    "load_listing",
    "normalize_employer",
    "register_spec",
    "search_targets",
]
