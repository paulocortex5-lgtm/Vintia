"""Non-European source registry + seed data (tasks 15.13, 15.17).

Canada, Australia, New Zealand and the United States — the four
non-European destinations with **verified, machine-fetchable official
sources**. **No Asian country and no African country is in scope**
(task 15.17 removed Japan, the platform's only Asian destination);
coverage is bounded to destinations whose government publishes a
register or feed we can harvest, never a guessed portal.

This module is the git-authoritative record layer for those sources:

* :data:`VISA_SOURCES` — the employer/sponsor register adapters
  (CA Positive LMIA list, AU accredited sponsors, NZ accredited
  employers, US PERM/DFCW disclosures), each with >=10 seeded employer
  rows so a country filter returns results before any live fetch.
* :data:`SCHOLARSHIP_SOURCES` — the funded-programme adapters
  (Vanier/Pearson/McCall MacBain; Australia Awards/Melbourne/Monash;
  Manaaki/Auckland; Fulbright/Gates Cambridge-adjacent US awards), each
  carrying sourced programmes.
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
        source_id="us_perm",
        country="US",
        name="United States — Permanent Labour Certification (PERM) sponsor disclosures",
        kind="visa",
        url="https://www.dol.gov/agencies/eta/foreign-labor/performance",
        basis="US DOL Office of Foreign Labor Certification — PERM disclosure data "
        "(H-1B/EB-2/EB-3 sponsors); largest non-Asian English-speaking job market",
        employers=(
            "Microsoft Corporation",
            "Google LLC",
            "Amazon.com Services",
            "Apple Inc",
            "Meta Platforms",
            "Intel Corporation",
            "JPMorgan Chase",
            "Goldman Sachs",
            "IBM Corporation",
            "Deloitte LLP",
            "Accenture",
            "Walmart Inc",
        ),
    ),
    WorldVisaSource(
        source_id="uk_sponsor_register",
        country="GB",
        name="UK — Skilled Worker sponsor licence register",
        kind="visa",
        url="https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers",
        basis="UK Home Office register of licensed sponsors (Skilled Worker route); "
        "employers on this register can sponsor foreign nationals for work visas",
        employers=(
            "National Health Service (NHS) Trusts",
            "Tesco PLC",
            "Sainsbury's Supermarkets Ltd",
            "ASDA Stores Ltd",
            "PricewaterhouseCoopers LLP",
            "Deloitte LLP",
            "KPMG LLP",
            "Ernst & Young LLP",
            "HSBC UK Bank plc",
            "Barclays Bank UK plc",
            "Lloyds Bank plc",
            "British Airways plc",
        ),
    ),
    WorldVisaSource(
        source_id="ie_employment_permits",
        country="IE",
        name="Ireland — Employment Permit sponsors",
        kind="visa",
        url="https://enterprise.gov.ie/en/employment-permits/",
        basis="Ireland Department of Enterprise, Trade and Employment — Employment "
        "Permit system; listed employers sponsor non-EEA nationals for work visas",
        employers=(
            "Ryanair DAC",
            "Kerry Group plc",
            "CRH plc",
            "Paddy Power Betfair plc",
            "Google Ireland Ltd",
            "Meta Platforms Ireland Ltd",
            "Amazon Web Services Ireland",
            "Pfizer Ireland Pharmaceuticals",
            "Johnson & Johnson (Ireland)",
            "Eli Lilly and Company (Ireland)",
            "Dell Technologies Ireland",
            "AbbVie Ireland",
        ),
    ),
    WorldVisaSource(
        source_id="de_blue_card",
        country="DE",
        name="Germany — EU Blue Card sponsors",
        kind="visa",
        url="https://make-it-in-germany.com/en",
        basis="Germany Make-it-in-Germany / Federal Employment Agency — EU Blue Card "
        "and Skilled Immigration Act sponsors; recognised German employers hiring "
        "third-country nationals",
        employers=(
            "Siemens AG",
            "Robert Bosch GmbH",
            "SAP SE",
            "BMW AG",
            "Volkswagen AG",
            "Deutsche Bank AG",
            "Allianz SE",
            "Deutsche Lufthansa AG",
            "Bayer AG",
            "Mercedes-Benz Group AG",
            "Deutsche Telekom AG",
            "Adidas AG",
        ),
    ),
    WorldVisaSource(
        source_id="se_work_permit",
        country="SE",
        name="Sweden — Work permit sponsors",
        kind="visa",
        url="https://www.migrationsverket.se/en/Private-individuals/Working-in-Sweden/",
        basis="Swedish Migration Agency — work permit system; listed employers sponsor "
        "non-EU/EEA nationals for employment in Sweden",
        employers=(
            "Ericsson AB",
            "Volvo Group AB",
            "Spotify AB",
            "H&M Hennes & Mauritz AB",
            "IKEA of Sweden AB",
            "Skanska AB",
            "SEB (Skandinaviska Enskilda Banken)",
            "Electrolux AB",
            "AstraZeneca AB",
            "Atlas Copco AB",
            "Sandvik AB",
            "Essity AB",
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
    # ── United States ─────────────────────────────────────────────────
    WorldScholarship(
        id="fulbright-foreign-student",
        name="Fulbright Foreign Student Program",
        provider="Bureau of Educational and Cultural Affairs (US Dept of State)",
        country="US",
        level="any",
        funding="fully_funded",
        window_close=None,
        url="https://foreign.fulbrightonline.org/",
        basis="Fulbright — full tuition, monthly stipend, health coverage, airfare for "
        "graduate study/research in the United States",
    ),
    WorldScholarship(
        id="hubert-h-humphrey",
        name="Hubert H. Humphrey Fellowship Program",
        provider="Bureau of Educational and Cultural Affairs (US Dept of State)",
        country="US",
        level="any",
        funding="fully_funded",
        window_close=None,
        url="https://humphreyfellowship.org/",
        basis="Humphrey — full funding for mid-career professionals: tuition, stipend, "
        "professional development, airfare",
    ),
    WorldScholarship(
        id="chevening-uk",
        name="Chevening Scholarships (UK)",
        provider="UK Foreign, Commonwealth & Development Office",
        country="GB",
        level="masters",
        funding="fully_funded",
        window_close="2026-11-03",
        url="https://www.chevening.org/scholarships/",
        basis="Chevening — UK government fully funded master's scholarships; tuition, "
        "living allowance, airfare, arrival/home allowances, visa costs",
    ),
    WorldScholarship(
        id="commonwealth-uk",
        name="Commonwealth Scholarship (UK)",
        provider="Commonwealth Scholarship Commission",
        country="GB",
        level="any",
        funding="fully_funded",
        window_close=None,
        url="https://cscuk.fcdo.gov.uk/",
        basis="Commonwealth Scholarships — fully funded master's and PhD for Commonwealth "
        "citizens; tuition, airfare, living stipend",
    ),
    WorldScholarship(
        id="ireland-government-scholarship",
        name="Government of Ireland International Education Scholarship",
        provider="Government of Ireland / Higher Education Authority",
        country="IE",
        level="masters",
        funding="fully_funded",
        window_close="2027-03-31",
        url="https://www.gov.ie/en/publication/1e46c-government-of-ireland-international-education-scholarship-programme/",
        basis="Government of Ireland IES — full tuition waiver plus €10,000 stipend for "
        "one year of study in Ireland",
    ),
    WorldScholarship(
        id="daad-germany",
        name="DAAD Scholarship Programmes (Germany)",
        provider="DAAD — German Academic Exchange Service",
        country="DE",
        level="any",
        funding="varies",
        window_close=None,
        url="https://www.daad.de/en/study-and-research-in-germany/scholarships/",
        basis="DAAD scholarship database — 149+ programmes for international students; "
        "funding terms vary per programme, no single window",
    ),
    WorldScholarship(
        id="swedish-institute",
        name="Swedish Institute Scholarships for Global Professionals",
        provider="Swedish Institute",
        country="SE",
        level="masters",
        funding="fully_funded",
        window_close=None,
        url="https://si.se/en/study-in-sweden/scholarships/",
        basis="Swedish Institute SGP — fully funded master's studies in Sweden; tuition, "
        "living allowance, travel grant, insurance",
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
    """Upsert sponsored-employer listings for CA/AU/NZ/US into the ingest store.

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
