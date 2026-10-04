"""Employer sponsor registers — task 2.3 (UK / DE / AU).

**What 2.3 is:** government lists of *employers licensed to sponsor
work visas*. They **badge** employers (`visa_sponsorship=True` on a
listing) — they are **never** used to drop jobs. All jobs from all
sources stay in the platform; sponsorship is a tag, not a gate
(product direction, session 7).

* **UK** — GOV.UK *Register of licensed sponsors: workers*: a CSV
  attachment on the publication page, refreshed almost daily (verified
  2026-10-02 update). Pipeline: publication page → first CSV href →
  download → normalised name set (:func:`fetch_uk_register`).
* **AU** — the official public register of approved sponsors is
  mandated by the Migration Amendment (Combatting Migrant Exploitation)
  Act 2026 (Royal Assent 2026-04-08, register required by 2026-10-08)
  but is **not yet published**. :func:`fetch_au_register` raises
  :class:`~engine.errors.RegisterPending` until Home Affairs ships it;
  callers skip badging instead of failing the run.
* **DE** — Germany publishes **no** employer sponsor register: the
  *Vorabzustimmung* (BA pre-approval) is granted per employer+employee
  pair and is not a public list. :data:`GERMANY_PUBLISHES_REGISTER` is
  the machine-readable statement of that fact; German sponsorship is
  judged per posting from the listing text.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, replace
from urllib.parse import urljoin

from ..errors import FetchError, RegisterPending
from ..logging_config import utc_now
from .fetch import Fetcher
from .portals.base import JobListing

#: GOV.UK publication page that carries the latest CSV attachment.
UK_PUBLICATION_URL = (
    "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
)

#: Germany publishes no employer-level register (documented fact).
GERMANY_PUBLISHES_REGISTER = False

#: Home Affairs register (expected once the 2026 Act commences).
AU_REGISTER_URL = "https://www.homeaffairs.gov.au/trav/visa-1/employ-sponsor"

#: Corporate suffixes ignored when comparing employer names.
_SUFFIXES = frozenset(
    {
        "ltd",
        "limited",
        "plc",
        "llp",
        "llc",
        "inc",
        "corp",
        "corporation",
        "co",
        "company",
        "gmbh",
        "ag",
        "sa",
        "sas",
        "bv",
        "nv",
        "oy",
        "ab",
        "as",
        "asa",
        "spa",
        "srl",
        "pte",
        "pty",
        "kk",
        "kg",
        "ou",
        "sarl",
        "uk",
        "the",
        "and",
        "of",
    }
)

_WORD = re.compile(r"[a-z0-9]+")

#: Listing text that clearly advertises sponsorship (tag = True only).
SPONSORSHIP_TEXT = re.compile(
    r"visa sponsorship|sponsor(?:s|ed|ing)?\s+(?:a\s+|your\s+)?visa|"
    r"skilled\s+worker\s+sponsor|we\s+will\s+sponsor",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SponsorRegister:
    """Normalised employer register for one country."""

    country: str  # ISO alpha-2
    source_url: str
    fetched_at: str  # YYYY-MM-DDTHH:MM:SSZ
    names: frozenset[str]  # normalised employer names
    raw_count: int  # rows in the source file

    def matches(self, employer: str) -> bool:
        """True when ``employer`` (fuzzy-normalised) is in the register."""
        return normalize_employer(employer) in self.names

    def __len__(self) -> int:
        return len(self.names)


def normalize_employer(name: str) -> str:
    """Casefold, drop punctuation and corporate suffixes for matching.

    ``"Acme Robotics Ltd"`` → ``"acme robotics"`` (and vice versa), so
    register lookups survive legal-form differences.
    """
    words = [w for w in _WORD.findall(name.casefold()) if w not in _SUFFIXES]
    return " ".join(words)


# ── UK: GOV.UK CSV register ───────────────────────────────────────────

_HREF_CSV = re.compile(r'href="([^"]+)"', re.IGNORECASE)


def resolve_uk_csv_url(page_html: str, *, base: str = UK_PUBLICATION_URL) -> str | None:
    """First CSV attachment href on the GOV.UK publication page.

    GOV.UK serves attachments either as ``/csv-preview/<hash>/...csv`` or
    asset links ending in ``.csv``; both are matched, and relative hrefs
    are resolved against the page URL.
    """
    for href in _HREF_CSV.findall(page_html):
        lowered = href.lower()
        if ".csv" in lowered or "/csv-preview/" in lowered:
            return urljoin(base, href)
    return None


def _name_column(fieldnames: list[str]) -> str:
    for column in fieldnames:
        lowered = column.casefold()
        if "organisation" in lowered or "organization" in lowered or "name" in lowered:
            return column
    return fieldnames[0]


def fetch_uk_register(
    fetcher: Fetcher, *, publication_url: str = UK_PUBLICATION_URL
) -> SponsorRegister:
    """Download and parse the UK register of licensed sponsors (CSV)."""
    page = fetcher.fetch(publication_url)
    csv_url = resolve_uk_csv_url(page.content, base=publication_url)
    if csv_url is None:
        raise FetchError(
            "no CSV attachment found on the UK register page",
            code="register_missing_link",
            url=publication_url,
        )
    result = fetcher.fetch(csv_url)
    reader = csv.DictReader(io.StringIO(result.content))
    if not reader.fieldnames:
        raise FetchError("UK register CSV has no header row", url=csv_url)
    column = _name_column(list(reader.fieldnames))
    raw_rows = 0
    names: set[str] = set()
    for row in reader:
        raw_rows += 1
        value = (row.get(column) or "").strip()
        normalised = normalize_employer(value)
        if normalised:
            names.add(normalised)
    return SponsorRegister(
        country="GB",
        source_url=csv_url,
        fetched_at=utc_now(),
        names=frozenset(names),
        raw_count=raw_rows,
    )


# ── AU: mandated, not yet published ───────────────────────────────────


def fetch_au_register(fetcher: Fetcher) -> SponsorRegister:
    """Raise :class:`RegisterPending` until Home Affairs publishes.

    The register is legally mandated (Migration Amendment (Combatting
    Migrant Exploitation) Act 2026, s.140GD) with publication required
    no later than 2026-10-08; once live, replace this body with the
    same page→CSV pipeline used for the UK. ``fetcher`` is accepted now
    so call sites never change.
    """
    raise RegisterPending(
        "Australia's public sponsor register is not yet published "
        "(required by 2026-10-08); see " + AU_REGISTER_URL,
        url=AU_REGISTER_URL,
        deadline="2026-10-08",
    )


# ── tagging (never filtering) ─────────────────────────────────────────


def tag_from_register(listing: JobListing, *registers: SponsorRegister) -> JobListing:
    """Set ``visa_sponsorship=True`` when the employer is in a register.

    Absence from a register leaves the tag untouched (``None``) — it is
    **not** evidence of no sponsorship, and the listing is always
    returned (registers never drop jobs).
    """
    for register in registers:
        if register.matches(listing.company):
            return replace(listing, visa_sponsorship=True)
    return listing


def tag_from_text(listing: JobListing) -> JobListing:
    """Set ``visa_sponsorship=True`` when the posting advertises it."""
    if listing.visa_sponsorship is True:
        return listing
    haystack = f"{listing.title}\n{listing.description}"
    if SPONSORSHIP_TEXT.search(haystack):
        return replace(listing, visa_sponsorship=True)
    return listing


def badge(listing: JobListing, *registers: SponsorRegister) -> JobListing:
    """Apply both taggers in order; the listing always comes back."""
    return tag_from_text(tag_from_register(listing, *registers))
