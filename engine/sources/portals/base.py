"""Shared types for portal adapters (task 2.2).

W/G/L = **W**orkday, **G**reenhouse, **L**ever — the three ATS/portal
platforms that host the majority of employer career pages. The repo never
expanded the abbreviation; this reading was chosen because all three
expose machine-readable endpoints that can be exercised offline.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import ClassVar
from urllib.parse import urlsplit

from ..fetch import Fetcher


@dataclass(frozen=True)
class JobListing:
    """One job posting as normalised across the three portals."""

    portal: str  # "greenhouse" | "lever" | "workday"
    external_id: str
    title: str
    company: str  # board token / company slug / tenant
    location: str
    url: str  # canonical hosted URL for the posting
    posted_at: str | None = None  # YYYY-MM-DD when the portal provides it
    description: str = ""  # plain text; "" when the list endpoint omits it
    extra: dict[str, str] = field(default_factory=dict)


class PortalAdapter(ABC):
    """Contract every portal adapter implements."""

    #: short registry key, e.g. ``"greenhouse"``
    name: ClassVar[str] = ""
    #: host suffixes this adapter claims (matched on the last labels)
    domains: ClassVar[tuple[str, ...]] = ()

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self.fetcher = fetcher if fetcher is not None else Fetcher()

    def claims(self, url: str) -> bool:
        """True when ``url``'s host belongs to this portal."""
        host = (urlsplit(url).hostname or "").lower()
        return any(host == d or host.endswith("." + d) for d in self.domains)

    @abstractmethod
    def search(self, source: str, *, limit: int = 25) -> list[JobListing]:
        """List postings for ``source`` (board token / slug / tenant/site)."""

    @abstractmethod
    def load(self, url: str) -> JobListing:
        """Fetch one posting by its hosted URL."""

    def close(self) -> None:
        self.fetcher.close()


# ── parsing helpers shared by the adapters ────────────────────────────

_BLOCK_TAGS = frozenset(
    {"br", "p", "div", "ul", "ol", "li", "tr", "section", "article", "h1", "h2", "h3", "h4"}
)
_SKIP_TAGS = frozenset({"script", "style", "head"})


def strip_html(raw: str) -> str:
    """HTML → readable plain text (block tags become newlines).

    Entities must be decoded *before* calling (Greenhouse entity-encodes
    its ``content`` field); ``HTMLParser`` then converts any remaining
    charrefs in text nodes.
    """
    from html.parser import HTMLParser

    class _Extractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []
            self._skip = 0

        def handle_starttag(self, tag: str, attrs: list) -> None:
            if tag in _SKIP_TAGS:
                self._skip += 1
            elif not self._skip and tag in _BLOCK_TAGS:
                self.parts.append("\n")

        def handle_endtag(self, tag: str) -> None:
            if tag in _SKIP_TAGS and self._skip:
                self._skip -= 1
            elif not self._skip and tag in _BLOCK_TAGS:
                self.parts.append("\n")

        def handle_data(self, data: str) -> None:
            if not self._skip:
                self.parts.append(data)

    extractor = _Extractor()
    extractor.feed(raw)
    extractor.close()
    text = "".join(extractor.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_MONTH_DAY_YEAR = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})")
_DAY_MONTH_YEAR = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
_YEAR_MONTH_DAY = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


def _named_date(match: re.Match[str], month_first: bool) -> str | None:
    if month_first:
        month = _MONTHS.get(match.group(1).lower())
        day, year = int(match.group(2)), int(match.group(3))
    else:
        month = _MONTHS.get(match.group(2).lower())
        day, year = int(match.group(1)), int(match.group(3))
    if month is None:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def iso_date(value: str | None) -> str | None:
    """Best-effort ``value`` → ``YYYY-MM-DD``; ``None`` when unparseable.

    Parses ISO timestamps (with or without offsets) plus the plain
    English shapes the portals emit ("Aug 5, 2026", ...). Constructing
    :class:`datetime.date` directly keeps everything timezone-free.
    """
    if not value:
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        pass
    if month_first := _MONTH_DAY_YEAR.fullmatch(text):
        return _named_date(month_first, month_first=True)
    if day_first := _DAY_MONTH_YEAR.fullmatch(text):
        return _named_date(day_first, month_first=False)
    if iso := _YEAR_MONTH_DAY.fullmatch(text):
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))).isoformat()
        except ValueError:
            return None
    return None


def epoch_ms_date(ms: float) -> str:
    """Unix milliseconds → ``YYYY-MM-DD`` (UTC)."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).date().isoformat()
