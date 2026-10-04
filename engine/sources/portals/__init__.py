"""Portal adapters — W/G/L: Workday, Greenhouse, Lever (task 2.2).

Usage::

    from engine.sources.portals import adapter_for_url, load_listing

    listing = load_listing("https://job-boards.greenhouse.io/acme/jobs/123")
    adapter = adapter_for_url(url)
    jobs = adapter.search("acme", limit=10)   # board token / slug / tenant/site

Every adapter runs through :class:`engine.sources.Fetcher`, so the robots
gate, the per-domain rate limiter and the retry policy apply to all three
portals. No test ever hits the network: inject ``Fetcher(client=...)``.
"""

from __future__ import annotations

from ...errors import FetchError
from ..fetch import Fetcher
from .base import JobListing, PortalAdapter, filter_active, strip_html
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter
from .workday import WorkdayAdapter

#: Registration order decides who claims an ambiguous host (none overlap).
ADAPTER_TYPES: tuple[type[PortalAdapter], ...] = (
    GreenhouseAdapter,
    LeverAdapter,
    WorkdayAdapter,
)

__all__ = [
    "ADAPTER_TYPES",
    "GreenhouseAdapter",
    "JobListing",
    "LeverAdapter",
    "PortalAdapter",
    "WorkdayAdapter",
    "adapter_for_url",
    "adapters_for",
    "filter_active",
    "load_listing",
    "strip_html",
]


def adapters_for(fetcher: Fetcher | None = None) -> list[PortalAdapter]:
    """One live instance per registered portal."""
    return [adapter_type(fetcher) for adapter_type in ADAPTER_TYPES]


def adapter_for_url(url: str, fetcher: Fetcher | None = None) -> PortalAdapter | None:
    """The adapter whose domains claim ``url``; ``None`` when unknown."""
    for adapter in adapters_for(fetcher):
        if adapter.claims(url):
            return adapter
    return None


def load_listing(url: str, fetcher: Fetcher | None = None) -> JobListing:
    """Load one posting by hosted URL from whichever portal claims it.

    Raises :class:`FetchError` (``code="unsupported_portal"``) when no
    adapter recognises the host.
    """
    adapter = adapter_for_url(url, fetcher)
    if adapter is None:
        raise FetchError(f"no portal adapter for {url}", code="unsupported_portal", url=url)
    return adapter.load(url)
