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

 **All-country coverage** (session 7 follow-up): the module is not
 limited to UK/DE/AU — those are the three countries with *verified
 register facts*. :func:`register_spec` resolves **every** country of
 interest (all 50 in :data:`engine.sources.countries.EUROPE` plus AU)
 through a small explicit registry + the country database, and
 :func:`fetch_register` dispatches on it: published registers run the
 generic page→CSV pipeline, pending ones raise
 :class:`~engine.errors.RegisterPending`, and countries without a
 register yield an empty :class:`SponsorRegister` (nothing to badge;
 jobs are never dropped for that reason).
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from urllib.parse import urljoin

from ..errors import FetchError, RegisterPending
from ..logging_config import utc_now
from .countries import BY_ISO, REGISTER_NONE, REGISTER_PENDING, REGISTER_PUBLISHED
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


# ── all-country coverage (session 7 follow-up) ──────────────────────────


@dataclass(frozen=True)
class RegisterSpec:
    """How one country's register is obtained — or why it is not.

    The registry below covers **every** country of interest (the 50
    European entries of the country database plus AU). Countries with
    a *verified* register fact get an explicit entry; the rest resolve
    through :data:`engine.sources.countries.BY_ISO` and carry the
    country DB's publication status. A future published register for
    any country plugs in as a **data row** here (``status=`` +
    ``source_url`` on the publication page) — the generic page→CSV
    pipeline in :func:`fetch_uk_register` already takes the URL as a
    parameter.
    """

    iso2: str
    status: str  # REGISTER_PUBLISHED / REGISTER_PENDING / REGISTER_NONE
    source_url: str = ""
    deadline: str = ""
    note: str = ""


#: Explicitly verified register facts (the only three that need code).
_REGISTER_SPECS: dict[str, RegisterSpec] = {
    "GB": RegisterSpec(
        "GB",
        REGISTER_PUBLISHED,
        UK_PUBLICATION_URL,
        note="GOV.UK CSV attachment, refreshed almost daily (page → first CSV link)",
    ),
    "AU": RegisterSpec(
        "AU",
        REGISTER_PENDING,
        AU_REGISTER_URL,
        deadline="2026-10-08",
        note="Mandated by the Migration Amendment (Combatting Migrant Exploitation) Act 2026",
    ),
    "DE": RegisterSpec(
        "DE",
        REGISTER_NONE,
        note="Vorabzustimmung is granted per employer+employee and is not a public list",
    ),
}


def register_spec(iso2: str) -> RegisterSpec:
    """Register spec for any country of interest (all 50 European + AU).

    Every ISO code in :func:`engine.sources.countries.europe_iso2` plus
    ``"AU"`` resolves; anything else raises
    ``FetchError(code="register_country_unknown")`` — unknown is not
    silently assumed to be "no register".
    """
    code = iso2.upper()
    if code in _REGISTER_SPECS:
        return _REGISTER_SPECS[code]
    target = BY_ISO.get(code)
    if target is None:
        raise FetchError(
            f"{code!r} is not a country of interest (not in the 50-country database)",
            code="register_country_unknown",
        )
    return RegisterSpec(
        code, target.sponsor_register, "", note=target.notes or "no register documented"
    )


def empty_register(iso2: str) -> SponsorRegister:
    """An empty register: no names to badge, and no jobs are dropped."""
    return SponsorRegister(
        country=iso2,
        source_url="",
        fetched_at=utc_now(),
        names=frozenset(),
        raw_count=0,
    )


def fetch_register(iso2: str, fetcher: Fetcher) -> SponsorRegister:
    """Fetch one country's register (or an empty one when it publishes none).

    * ``published`` — run the generic page→CSV pipeline;
    * ``pending`` — raise :class:`RegisterPending` (legally mandated,
      not yet public; callers skip badging instead of failing);
    * ``none`` — return :func:`empty_register` (tagging simply finds no
      names; the listing is never dropped for that).
    """
    spec = register_spec(iso2)
    if spec.status == REGISTER_PUBLISHED:
        register = fetch_uk_register(fetcher, publication_url=spec.source_url)
        return replace(register, country=spec.iso2)
    if spec.status == REGISTER_PENDING:
        if spec.iso2 == "AU":
            return fetch_au_register(fetcher)
        raise RegisterPending(
            f"{spec.iso2} register is pending publication; see {spec.source_url}",
            url=spec.source_url,
            deadline=spec.deadline,
        )
    if spec.status == REGISTER_NONE:
        return empty_register(spec.iso2)
    raise FetchError(
        f"{spec.iso2} has unrecognised register status {spec.status!r}",
        code="register_status_unknown",
    )


def fetch_registers(iso2s: Iterable[str], fetcher: Fetcher) -> list[SponsorRegister]:
    """Bulk-fetch registers for many countries; pending ones are skipped.

    Pending skips are non-fatal by design (session 7 product direction):
    the returned registers simply carry fewer names until the pending
    registers publish.
    """
    registers: list[SponsorRegister] = []
    for code in iso2s:
        try:
            registers.append(fetch_register(code, fetcher))
        except RegisterPending:
            continue
    return registers


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
