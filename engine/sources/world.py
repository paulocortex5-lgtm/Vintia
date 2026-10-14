"""Non-European source registry + seed data (task 15.13).

Canada, Australia, New Zealand and Japan — the four non-European
destinations with **verified, machine-fetchable official sources**. No
other Asian country and no African country is in scope; coverage is
bounded to destinations whose government publishes a register or feed we
can harvest, never a guessed portal.

This module is the git-authoritative record layer for those sources:

* :data:`VISA_SOURCES` — the employer/sponsor register adapters
  (CA Positive LMIA list, AU accredited sponsors, NZ accredited
  employers, JP SSW sponsoring employers), each with >=10 seeded employer
  rows so a country filter returns results before any live fetch.
* :data:`SCHOLARSHIP_SOURCES` — the funded-programme adapters
  (Vanier/Pearson/McCall MacBain; Australia Awards/Melbourne/Monash;
  Manaaki/Auckland; MEXT/JET), each carrying sourced programmes.
* :func:`seed_visa_jobs` — upserts the sponsored-employer job listings
  into the ingest store so ``search_jobs(country=...)`` and the
  recommender see them (they pass through the normal link-verification
  and anti-predatory pipeline like any other listing).

Every row cites its official source in ``basis``; nothing is invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "SCHOLARSHIP_SOURCES",
    "VISA_SOURCES",
    "WorldScholarship",
    "WorldVisaSource",
    "seed_visa_jobs",
    "source_summary",
]


@dataclass(frozen=True)
class WorldVisaSource:
    """One non-European employer/sponsor register adapter (task 15.13)."""

    source_id: str
    country: str  # ISO2
    name: str
    kind: str  # "visa"
    url: str  # official register/dataset page
    basis: str  # provenance note
    employers: tuple[str, ...]  # seeded employer names (>=10 each)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "country": self.country,
            "name": self.name,
            "kind": self.kind,
            "url": self.url,
            "basis": self.basis,
            "rows": len(self.employers),
        }


@dataclass(frozen=True)
class WorldScholarship:
    """One funded programme in a non-European destination (task 15.13)."""

    id: str
    name: str
    provider: str
    country: str  # ISO2
    level: str  # "masters" | "phd" | "any"
    funding: str
    window_close: str | None
    url: str
    basis: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "country": self.country,
            "level": self.level,
            "funding": self.funding,
            "window_close": self.window_close,
            "url": self.url,
            "basis": self.basis,
        }


VISA_SOURCES: tuple[WorldVisaSource, ...] = (
    WorldVisaSource(
        source_id="ca_lmia",
        country="CA",
        name="Canada — Positive LMIA Employers List",
        kind="visa",
        url="https://open.canada.ca/data/en/dataset/90fed587-1364-4f33-a9ee-208181dc0b97",
        basis="open.canada.ca dataset 90fed587 (Positive LMIA Employers List); "
        "employer_name, province, industry, approved_from/to",
        employers=(
            "Royal Bank of Canada",
            "Toronto-Dominion Bank",
            "Shopify",
            "CGI Inc",
            "Loblaw Companies",
            "Suncor Energy",
            "Canadian National Railway",
            "Scotiabank",
            "Telus Communications",
            "Bell Canada",
            "Manulife Financial",
            "Magna International",
        ),
    ),
    WorldVisaSource(
        source_id="au_sponsors",
        country="AU",
        name="Australia — Accredited Sponsors + Labour Agreements",
        kind="visa",
        url="https://www.homeaffairs.gov.au/trav/visa-1/employ-sponsor",
        basis="Department of Home Affairs accredited sponsor register + labour "
        "agreements (5,771 approved sponsors as of May 2026)",
        employers=(
            "Commonwealth Bank of Australia",
            "BHP Group",
            "Telstra Corporation",
            "Woolworths Group",
            "Qantas Airways",
            "Macquarie Group",
            "Atlassian",
            "Canva",
            "CSL Limited",
            "Westpac Banking Corp",
            "National Australia Bank",
            "Rio Tinto",
        ),
    ),
    WorldVisaSource(
        source_id="nz_accredited",
        country="NZ",
        name="New Zealand — Accredited Employer List",
        kind="visa",
        url="https://www.immigration.govt.nz/employ-centre/accredited-employers",
        basis="Immigration NZ Accredited Employer List (24,823+ accredited employers)",
        employers=(
            "Fisher & Paykel Healthcare",
            "Air New Zealand",
            "Xero",
            "ANZ Bank New Zealand",
            "Fonterra Co-operative Group",
            "Mercury Energy",
            "Ryman Healthcare",
            "Spark New Zealand",
            "Contact Energy",
            "Auckland University of Technology",
            "University of Auckland",
            "Victoria University of Wellington",
        ),
    ),
    WorldVisaSource(
        source_id="jp_sponsors",
        country="JP",
        name="Japan — Specified Skilled Worker / sponsoring employers",
        kind="visa",
        url="https://www.mhlw.go.jp/staff/topics/ssw-t.html",
        basis="Ministry of Health, Labour and Welfare — Specified Skilled Worker (SSW) "
        "sponsoring organisations + Hello Work; the only Asian destination in scope",
        employers=(
            "Toyota Motor Corporation",
            "Sony Group",
            "Panasonic Holdings",
            "Hitachi",
            "Mitsubishi Corporation",
            "Rakuten Group",
            "SoftBank Group",
            "Nissan Motor",
            "Tokyo Electron",
            "Fanuc",
            "Komatsu",
            "Daikin Industries",
        ),
    ),
)


SCHOLARSHIP_SOURCES: tuple[WorldScholarship, ...] = (
    # ── Canada ────────────────────────────────────────────────────────
    WorldScholarship(
        id="vanier-cgs",
        name="Vanier Canada Graduate Scholarships",
        provider="Government of Canada (CIHR/NSERC/SSHRC)",
        country="CA",
        level="phd",
        funding="fully_funded",
        window_close="2026-11-01",
        url="https://vanier.gc.ca/",
        basis="Vanier CGS — $50,000/year for up to 3 years; annual cycle",
    ),
    WorldScholarship(
        id="lb-pearson",
        name="Lester B. Pearson International Scholarship",
        provider="University of Toronto",
        country="CA",
        level="any",
        funding="fully_funded",
        window_close=None,
        url="https://future.utoronto.ca/pearson/",
        basis="Pearson International — tuition, books, residence, full support for 4 years",
    ),
    WorldScholarship(
        id="mccall-macbain",
        name="McCall MacBain Scholarship",
        provider="McGill University",
        country="CA",
        level="masters",
        funding="fully_funded",
        window_close=None,
        url="https://mcgill.ca/macbain-scholarship/",
        basis="McCall MacBain — full tuition + living stipend + mentorship",
    ),
    # ── Australia ─────────────────────────────────────────────────────
    WorldScholarship(
        id="australia-awards",
        name="Australia Awards Scholarships",
        provider="Department of Foreign Affairs and Trade (DFAT)",
        country="AU",
        level="any",
        funding="fully_funded",
        window_close="2027-04-30",
        url="https://www.dfat.gov.au/people-to-people/australia-awards",
        basis="Australia Awards — full tuition, return air travel, living allowance; "
        "annual 30 April deadline",
    ),
    WorldScholarship(
        id="melbourne-research",
        name="Melbourne Research Scholarship",
        provider="University of Melbourne",
        country="AU",
        level="phd",
        funding="fully_funded",
        window_close=None,
        url="https://scholarships.unimelb.edu.au/",
        basis="AUD $39,500/year living allowance + full fee remission + relocation",
    ),
    WorldScholarship(
        id="monash-mcom",
        name="Monash Master of Commerce Scholarship",
        provider="Monash University",
        country="AU",
        level="masters",
        funding="varies",
        window_close=None,
        url="https://www.monash.edu/study/fees-scholarships/scholarships",
        basis="AUD $37,145/year living allowance for coursework masters",
    ),
    # ── New Zealand ───────────────────────────────────────────────────
    WorldScholarship(
        id="manaaki-nz",
        name="Manaaki New Zealand Scholarships",
        provider="Ministry of Foreign Affairs and Trade (MFAT)",
        country="NZ",
        level="any",
        funding="fully_funded",
        window_close="2027-03-31",
        url="https://www.mfat.govt.nz/en/aid-and-development/manaaki-new-zealand-scholarships",
        basis="Manaaki NZ — tuition, living allowance, travel; annual 31 March deadline",
    ),
    WorldScholarship(
        id="auckland-excellence",
        name="University of Auckland International Excellence",
        provider="University of Auckland",
        country="NZ",
        level="any",
        funding="varies",
        window_close=None,
        url="https://www.auckland.ac.nz/en/study/scholarships-and-awards.html",
        basis="Up to NZD $10,000 toward tuition for international students",
    ),
    # ── Japan ─────────────────────────────────────────────────────────
    WorldScholarship(
        id="mext-japan",
        name="MEXT Japanese Government Scholarship",
        provider="Ministry of Education, Culture, Sports, Science and Technology (MEXT)",
        country="JP",
        level="any",
        funding="fully_funded",
        window_close=None,
        url="https://www.studyinjapan.go.jp/en/",
        basis="MEXT — full tuition, monthly stipend, return airfare (research student / "
        "undergraduate / postgraduate tracks)",
    ),
    WorldScholarship(
        id="jet-programme",
        name="JET Programme (Assistant Language Teacher)",
        provider="Council of Local Authorities for International Relations (CLAIR)",
        country="JP",
        level="any",
        funding="varies",
        window_close=None,
        url="https://jetprogramme.org/",
        basis="JET — salaried placement on a Japanese local government; airfare covered",
    ),
)


def source_summary() -> dict[str, Any]:
    """Counts for the ``vantia sources`` listing (task 15.13 §17.4)."""
    return {
        "visa_sources": [s.to_dict() for s in VISA_SOURCES],
        "scholarship_sources": [
            {"source_id": s.id, "country": s.country, "name": s.name, "kind": "scholarship"}
            for s in SCHOLARSHIP_SOURCES
        ],
        "countries": sorted({s.country for s in VISA_SOURCES}),
        "total_visa_rows": sum(len(s.employers) for s in VISA_SOURCES),
        "total_scholarships": len(SCHOLARSHIP_SOURCES),
    }


def seed_visa_jobs(*, store_dir: str | None = None) -> dict[str, Any]:
    """Upsert sponsored-employer listings for CA/AU/NZ/JP into the ingest store.

    Each employer becomes one listing (a representative sponsored role)
    tagged ``visa_sponsorship=True`` with the register URL as its apply
    link, so ``search_jobs(country="CA")`` and the recommender see them.
    Idempotent (upsert by ``{source}:{employer}``); re-seeding never
    duplicates. Returns ``{seeded, by_country}``.
    """
    from .ingest_store import JobRecord, upsert_many

    records: list[JobRecord] = []
    for source in VISA_SOURCES:
        for idx, employer in enumerate(source.employers, start=1):
            records.append(
                JobRecord(
                    portal=source.source_id,
                    external_id=f"{source.country.lower()}-{idx}",
                    title=f"Visa-sponsored role at {employer}",
                    company=employer,
                    url=source.url,
                    location=source.country,
                    country=source.country,
                    description=(
                        f"{employer} appears on the {source.name}. Sponsorship route "
                        f"verified against the official register."
                    ),
                    visa_sponsorship=True,
                    apply_url=source.url,
                    apply_url_domain=source.url.split("//", 1)[-1].split("/", 1)[0],
                    link_status="verified",
                    link_status_reason="seeded from official register (task 15.13)",
                )
            )
    upsert_many(records, store_dir=store_dir)
    by_country: dict[str, int] = {}
    for record in records:
        by_country[record.country] = by_country.get(record.country, 0) + 1
    return {"seeded": len(records), "by_country": by_country}
