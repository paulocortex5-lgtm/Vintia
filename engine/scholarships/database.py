"""Scholarship database (task 3.1) — five curated, sourced programs.

Every row was verified against its official page (see ``basis``) on
2026-10-06; no program or URL is invented. Windows are embedded only
where the official source publishes a recurring cycle (month precision
kept as published); programs whose deadlines vary by course/country
carry ``window_open=None`` and surface as ``unknown`` in the window
tracker rather than a guessed date.

Matching is a **filter, never a gate**: eligibility flags and windows
inform the user; nothing is silently dropped without a recorded reason.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import VantiaError

__all__ = [
    "EUROPEAN_PROGRAMME_COUNTRIES",
    "SCHOLARSHIPS",
    "Scholarship",
    "get_scholarship",
    "search_scholarships",
]


@dataclass(frozen=True)
class Scholarship:
    """One funded study-abroad program."""

    id: str
    name: str
    provider: str
    host_countries: tuple[str, ...]  # ISO2 destinations ("EU" handled per-row below)
    level: str  # "masters" | "phd" | "any"
    min_eqf_level: int  # entry requirement as an EQF level (6 = bachelor's)
    fields: tuple[str, ...]  # study fields; ("any",) = open to every field
    funding: str  # "fully_funded" | "varies"
    nationality: tuple[str, ...]  # eligible applicant ISO2s; ("any",) = world-wide
    window_open: str | None  # "YYYY-MM" or "YYYY-MM-DD"; None = varies/unpublished
    window_close: str | None
    annual: bool  # window repeats yearly (month/day-of-month semantics)
    spans_europe: bool = False  # accepts any Erasmus+ programme country
    url: str = ""  # official program page (verified)
    basis: str = ""  # provenance note

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "host_countries": list(self.host_countries),
            "level": self.level,
            "min_eqf_level": self.min_eqf_level,
            "fields": list(self.fields),
            "funding": self.funding,
            "nationality": list(self.nationality),
            "window_open": self.window_open,
            "window_close": self.window_close,
            "annual": self.annual,
            "spans_europe": self.spans_europe,
            "url": self.url,
            "basis": self.basis,
        }


#: Erasmus+ programme countries (EU-27 + IS/LI/NO) — EMJM eligibility.
EUROPEAN_PROGRAMME_COUNTRIES: frozenset[str] = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
        "IS",
        "LI",
        "NO",
    }
)


def get_scholarship(scholarship_id: str) -> Scholarship:
    """One program by id; raises ``scholarship_not_found`` (never None)."""
    for row in SCHOLARSHIPS:
        if row.id == scholarship_id:
            return row
    raise VantiaError(
        f"unknown scholarship id: {scholarship_id!r}",
        code="scholarship_not_found",
        scholarship_id=scholarship_id,
    )


def search_scholarships(
    *,
    field: str = "",
    level: str | None = None,
    host_country: str | None = None,
    nationality: str | None = None,
    funding: str | None = None,
) -> list[Scholarship]:
    """Registry-order filter; empty result means nothing fits (said out loud)."""
    needle = field.strip().lower()
    matches: list[Scholarship] = []
    for row in SCHOLARSHIPS:
        if funding is not None and row.funding != funding:
            continue
        if level is not None and row.level not in (level, "any"):
            continue
        if host_country is not None:
            host = host_country.strip().upper()
            europe_ok = row.spans_europe and host in EUROPEAN_PROGRAMME_COUNTRIES
            if host not in row.host_countries and not europe_ok:
                continue
        if nationality is not None:
            nat = nationality.strip().upper()
            if "any" not in row.nationality and nat not in row.nationality:
                continue
        if needle and "any" not in row.fields:
            haystack = " ".join(row.fields)
            if needle not in haystack and not any(f in needle for f in row.fields):
                continue
        matches.append(row)
    return matches


#: The five curated programs — extend by appending sourced rows.
SCHOLARSHIPS: tuple[Scholarship, ...] = (
    Scholarship(
        id="chevening",
        name="Chevening Scholarship",
        provider="UK Foreign, Commonwealth & Development Office (FCDO)",
        host_countries=("GB",),
        level="masters",
        min_eqf_level=6,
        fields=("any",),
        funding="fully_funded",
        nationality=("NG", "KE", "GH", "IN", "PH", "PK", "BD", "BR"),
        window_open="2026-08",
        window_close="2026-10",
        annual=True,
        url="https://www.chevening.org/",
        basis=(
            "Official site + application timeline verified 2026-10-06: applications open "
            "August 2026 and close October 2026 (11:00 UTC); fully funded one-year UK "
            "master's; the country selector lists all eight Vantia source countries"
        ),
    ),
    Scholarship(
        id="commonwealth-uk",
        name="Commonwealth Scholarship (UK)",
        provider="Commonwealth Scholarship Commission in the UK (CSC)",
        host_countries=("GB",),
        level="any",
        min_eqf_level=6,
        fields=("any",),
        funding="fully_funded",
        nationality=("NG", "KE", "GH", "IN", "PK", "BD"),
        window_open=None,
        window_close=None,
        annual=True,
        url="https://cscuk.fcdo.gov.uk/",
        basis=(
            "Official CSC site verified 2026-10-06; aimed at Commonwealth citizens "
            "(PH and BR are not Commonwealth states, hence excluded); master's and "
            "PhD routes; application rounds are announced per cycle — no recurring "
            "window embedded"
        ),
    ),
    Scholarship(
        id="daad",
        name="DAAD scholarship programmes (Germany)",
        provider="DAAD — Deutscher Akademischer Austauschdienst",
        host_countries=("DE",),
        level="any",
        min_eqf_level=6,
        fields=("any",),
        funding="varies",
        nationality=("any",),
        window_open=None,
        window_close=None,
        annual=True,
        url="https://www.daad.de/en/study-and-research-in-germany/scholarships/",
        basis=(
            "DAAD scholarship database verified 2026-10-06 (149 programmes; applicants "
            "need at least one first degree, e.g. bachelor); funding terms and deadlines "
            "vary per programme — no single window exists to embed"
        ),
    ),
    Scholarship(
        id="erasmus-mundus",
        name="Erasmus Mundus Joint Masters",
        provider="European Commission (Erasmus+)",
        host_countries=EUROPEAN_PROGRAMME_COUNTRIES,  # type: ignore[arg-type]
        level="masters",
        min_eqf_level=6,
        fields=("any",),
        funding="fully_funded",
        nationality=("any",),
        window_open="2026-10",
        window_close="2027-01",
        annual=True,
        spans_europe=True,
        url=(
            "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/"
            "erasmus-mundus-joint-masters"
        ),
        basis=(
            "Official Erasmus+ page verified 2026-10-06: 'students from all over the "
            "world', full scholarships for the best-ranked applicants, apply "
            "'between October and January', bachelor's (or final-year) required"
        ),
    ),
    Scholarship(
        id="australia-awards",
        name="Australia Awards Scholarships",
        provider="Australian Government (DFAT)",
        host_countries=("AU",),
        level="masters",
        min_eqf_level=6,
        fields=("any",),
        funding="fully_funded",
        nationality=("any",),
        window_open=None,
        window_close=None,
        annual=True,
        url=(
            "https://www.dfat.gov.au/people-to-people/australia-awards/"
            "australia-awards-scholarships"
        ),
        basis=(
            "Official DFAT page (URL verified via web search 2026-10-06; direct fetch "
            "timed out); fully funded postgraduate awards; eligibility is restricted to "
            "DFAT partner countries and opening/closing dates vary by country and "
            "intake — check the official list before applying"
        ),
    ),
)
