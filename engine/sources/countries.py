"""European search database + country targeting (product direction, session 7).

Scope decisions (recorded so future sessions do not relitigate them):

* **All European countries are listed** — EU-27, EFTA/EEA, UK, Western
  Balkans, Eastern Europe, Caucasus/Transcontinental and the
  microstates: 50 entries, documented in :data:`EUROPE`.
* **Jobs are never filtered by sponsorship.** ``sponsor_register`` only
  says whether a country *publishes* an employer register we can use to
  **tag** listings (``visa_sponsorship=True``) — it never hides jobs.
* **Targeting** — :meth:`CountryTarget.score` ranks countries by how
  much opportunity we can actually reach (machine-fetchable government
  sources) minus competition (unemployment rate, once populated from
  Eurostat ``une_rt_a``; ``None`` until a verified snapshot is embedded
  — the field exists so enrichment is a data change, not a code change).
* ``pes_url`` is the official public employment service portal for
  humans/HTML fallbacks; ``gov_jobs_api`` is a machine endpoint our
  :class:`~engine.sources.fetch.Fetcher` can call directly.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Register publication states for employer sponsor registers.
REGISTER_PUBLISHED = "published"
REGISTER_PENDING = "pending"
REGISTER_NONE = "none"


@dataclass(frozen=True)
class CountryTarget:
    """One European country in the search database."""

    iso2: str
    name: str
    pes_url: str  # official public employment portal ("" = not catalogued yet)
    gov_jobs_api: str  # machine-readable jobs endpoint ("" = none verified yet)
    eu_eea: bool  # free movement / single-market relevance
    sponsor_register: str  # REGISTER_* — publication status, NOT a job filter
    unemployment_rate: float | None = None  # % of labour force (Eurostat hook)
    notes: str = ""

    def score(self) -> float:
        """Targeting score: reachable opportunity minus competition.

        Higher = more opportunity we can fetch + (when stats are
        populated) less competition. Structural signals first, labour
        market stats refine the rank:

        * +3.0 machine-fetchable government jobs API (we can harvest it)
        * +1.0 official public employment portal catalogued
        * +2.0 employer sponsor register published (+0.5 pending)
        * +1.0 EU/EEA (free movement for our users)
        * −unemployment/10 once a verified rate exists (lower joblessness
          ≈ fewer applicants per opening ⇒ less competition)
        """
        value = 0.0
        if self.gov_jobs_api:
            value += 3.0
        if self.pes_url:
            value += 1.0
        if self.sponsor_register == REGISTER_PUBLISHED:
            value += 2.0
        elif self.sponsor_register == REGISTER_PENDING:
            value += 0.5
        if self.eu_eea:
            value += 1.0
        if self.unemployment_rate is not None:
            value -= min(5.0, self.unemployment_rate / 10.0)
        return round(value, 2)


def _c(
    iso2: str,
    name: str,
    pes: str = "",
    api: str = "",
    eu_eea: bool = False,
    register: str = REGISTER_NONE,
    notes: str = "",
) -> CountryTarget:
    return CountryTarget(iso2, name, pes, api, eu_eea, register, None, notes)


# ── the database ──────────────────────────────────────────────────────
# (iso2, name, pes_url, gov_jobs_api, eu_eea, sponsor_register, notes)
# Register statuses: UK publishes daily (GOV.UK CSV); every other
# European country currently has no public employer sponsor register
# (Germany: "Vorabzustimmung" is granted per employer+employee and is
# not published as a list).

EUROPE: tuple[CountryTarget, ...] = (
    # ── EU-27 (all eu_eea) ────────────────────────────────────────────
    _c("AT", "Austria", "https://www.ams.at", eu_eea=True),
    _c("BE", "Belgium", "", eu_eea=True, notes="regional services: VDAB, Le Forem, AViQ, ADEM"),
    _c("BG", "Bulgaria", "", eu_eea=True, notes="Agency for Employment (az.government.bg)"),
    _c("HR", "Croatia", "https://burzarada.hzz.hr", eu_eea=True),
    _c("CY", "Cyprus", "", eu_eea=True, notes="Labour Department, Ministry of Labour"),
    _c("CZ", "Czechia", "https://www.uradprace.cz", eu_eea=True),
    _c("DK", "Denmark", "https://www.jobnet.dk", eu_eea=True),
    _c("EE", "Estonia", "https://www.tootukassa.ee", eu_eea=True),
    _c("FI", "Finland", "https://tyomarkkinatori.fi", eu_eea=True),
    _c(
        "FR",
        "France",
        "https://www.francetravail.fr",
        eu_eea=True,
        notes="France Travail has an OAuth API; portal is the fallback",
    ),
    _c(
        "DE",
        "Germany",
        "https://www.arbeitsagentur.de/jobsuche",
        "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs",
        eu_eea=True,
        notes="no public employer sponsor register (Vorabzustimmung is individual); "
        "sponsorship judged per posting",
    ),
    _c("GR", "Greece", "https://www.eseis.gr", eu_eea=True),
    _c("HU", "Hungary", "", eu_eea=True, notes="National Public Employment Service (OFOG)"),
    _c("IE", "Ireland", "https://www.services.mywelfare.ie", eu_eea=True),
    _c("IT", "Italy", "https://portaleimpiego.lavoro.gov.it", eu_eea=True),
    _c("LV", "Latvia", "https://www.nva.gov.lv", eu_eea=True),
    _c("LT", "Lithuania", "https://www.uzt.lt", eu_eea=True),
    _c("LU", "Luxembourg", "https://www.adem.lu", eu_eea=True),
    _c("MT", "Malta", "https://jobsplus.gov.mt", eu_eea=True),
    _c(
        "NL",
        "Netherlands",
        "https://www.werk.nl",
        eu_eea=True,
        notes="UWV; Werkgevers service points expose vacancy feeds",
    ),
    _c("PL", "Poland", "https://praca.gov.pl", eu_eea=True),
    _c("PT", "Portugal", "https://www.iefp.pt", eu_eea=True),
    _c("RO", "Romania", "https://www.anofm.ro", eu_eea=True),
    _c("SK", "Slovakia", "https://www.upsvar.sk", eu_eea=True),
    _c("SI", "Slovenia", "https://www.ess.gov.si", eu_eea=True),
    _c("ES", "Spain", "https://www.sepe.es", eu_eea=True),
    _c(
        "SE",
        "Sweden",
        "https://arbetsformedlingen.se",
        eu_eea=True,
        notes="Arbetsförmedlingen publishes open data feeds",
    ),
    # ── EFTA / EEA + Switzerland + UK ─────────────────────────────────
    _c("IS", "Iceland", "https://www.vinnumalastofnun.is", eu_eea=True),
    _c("LI", "Liechtenstein", "https://www.arbeitsamt.li", eu_eea=True),
    _c("NO", "Norway", "https://www.nav.no", eu_eea=True),
    _c(
        "CH",
        "Switzerland",
        "https://www.jobroom.admin.ch",
        notes="not EEA; bilateral free movement with the EU",
    ),
    _c(
        "GB",
        "United Kingdom",
        "https://www.findajob.dwp.gov.uk",
        "",
        register=REGISTER_PUBLISHED,
        notes="GOV.UK publishes the sponsor register CSV daily (task 2.3)",
    ),
    # ── Western Balkans ───────────────────────────────────────────────
    _c("AL", "Albania", "", notes="public employment service AKPP"),
    _c("BA", "Bosnia and Herzegovina", "", notes="entity-level services (fzzz.ba, zavod)"),
    _c("XK", "Kosovo", "", notes="Kosovo Employment Agency"),
    _c("ME", "Montenegro", "", notes="ZZZ CG"),
    _c("MK", "North Macedonia", "https://www.vrabotuvanje.gov.mk"),
    _c("RS", "Serbia", "", notes="National Employment Service (nsz.gov.rs)"),
    # ── Eastern Europe ────────────────────────────────────────────────
    _c("UA", "Ukraine", "https://www.dcz.gov.ua"),
    _c("BY", "Belarus", ""),
    _c("MD", "Moldova", ""),
    _c("RU", "Russia", "https://trudvsem.ru"),
    # ── Caucasus / transcontinental ───────────────────────────────────
    _c("GE", "Georgia", ""),
    _c("AM", "Armenia", ""),
    _c("AZ", "Azerbaijan", ""),
    _c("TR", "Türkiye", "https://www.iskur.gov.tr"),
    # ── microstates ───────────────────────────────────────────────────
    _c("AD", "Andorra"),
    _c("MC", "Monaco"),
    _c("SM", "San Marino"),
    _c("VA", "Vatican City", notes="no labour market"),
)

#: Fast lookup by ISO 3166-1 alpha-2.
BY_ISO: dict[str, CountryTarget] = {entry.iso2: entry for entry in EUROPE}


def search_targets(
    *,
    iso2_filter: set[str] | None = None,
    eu_eea_only: bool = False,
    with_api_only: bool = False,
) -> list[CountryTarget]:
    """Rank countries for the current search policy (best first).

    * ``iso2_filter`` — restrict to specific countries (the "pinpoint"
      use case: only the countries the user selected);
    * ``eu_eea_only`` / ``with_api_only`` — structural pre-filters;
    * ordering — :meth:`CountryTarget.score` descending, name ascending
      as a stable tiebreak. **No country is ever excluded because it
      lacks a sponsor register** — sponsorship is a tag, not a gate.
    """
    targets = list(EUROPE)
    if iso2_filter is not None:
        wanted = {code.upper() for code in iso2_filter}
        targets = [t for t in targets if t.iso2 in wanted]
    if eu_eea_only:
        targets = [t for t in targets if t.eu_eea]
    if with_api_only:
        targets = [t for t in targets if t.gov_jobs_api]
    return sorted(targets, key=lambda t: (-t.score(), t.name))


def europe_iso2() -> frozenset[str]:
    """All ISO codes in the database (the completeness contract)."""
    return frozenset(BY_ISO)
