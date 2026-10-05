"""Sponsor-register tests — task 2.3 (UK CSV / AU pending / DE none / all-country dispatch).

Registers TAG employers as able to sponsor; they never drop jobs
(product direction, session 7). All HTTP via MockTransport.
"""

from dataclasses import replace

import httpx
import pytest

from engine.errors import FetchError, RegisterPending
from engine.sources import Fetcher, badge, fetch_au_register, fetch_uk_register
from engine.sources.countries import (
    EUROPE,
    REGISTER_NONE,
    REGISTER_PENDING,
    REGISTER_PUBLISHED,
    europe_iso2,
)
from engine.sources.portals import JobListing
from engine.sources.ratelimit import DomainRateLimiter
from engine.sources.registers import (
    GERMANY_PUBLISHES_REGISTER,
    SponsorRegister,
    fetch_register,
    fetch_registers,
    normalize_employer,
    register_spec,
    resolve_uk_csv_url,
)

PAGE_HTML = (
    '<html><body><a href="/csv-preview/abc123/Register_of_Worker_sponsors.csv">'
    "CSV , 10.4 MB</a></body></html>"
)
CSV_BODY = (
    "Organisation name,Rating,City,Worker categories\n"
    "Acme Robotics Ltd,A,London,Skilled Worker\n"
    "Beta Health PLC,B,Manchester,Charity\n"
)


def build(handler) -> Fetcher:
    def combined(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return handler(request)

    limiter = DomainRateLimiter(min_interval_sec=0.0, max_per_day=10**6, sleep=lambda _s: None)
    return Fetcher(
        client=httpx.Client(transport=httpx.MockTransport(combined)),
        limiter=limiter,
        retries=1,
        sleep=lambda _s: None,
    )


def test_resolve_uk_csv_url_relative_and_absolute():
    assert resolve_uk_csv_url(PAGE_HTML).endswith(
        "/csv-preview/abc123/Register_of_Worker_sponsors.csv"
    )
    absolute = '<a href="https://assets.publishing.service.gov.uk/media/x.csv">x</a>'
    assert resolve_uk_csv_url(absolute) == "https://assets.publishing.service.gov.uk/media/x.csv"
    assert resolve_uk_csv_url('<a href="/government/other-page">no csv</a>') is None


def test_fetch_uk_register_parses_and_normalises():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("/register-of-licensed-sponsors-workers"):
            return httpx.Response(200, text=PAGE_HTML)
        return httpx.Response(200, text=CSV_BODY)

    register = fetch_uk_register(build(handler))
    assert register.country == "GB"
    assert register.raw_count == 2
    assert len(register) == 2
    assert register.matches("ACME ROBOTICS")  # case-insensitive
    assert register.matches("Acme Robotics Limited")  # corporate suffix dropped
    assert not register.matches("Gamma Industries")
    assert len(seen) == 2, "publication page then CSV"


def test_uk_register_without_csv_link_is_an_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><a href='/other'>x</a></html>")

    with pytest.raises(FetchError) as excinfo:
        fetch_uk_register(build(handler))
    assert excinfo.value.code == "register_missing_link"


def test_au_register_is_pending_not_fatal():
    with pytest.raises(RegisterPending) as excinfo:
        fetch_au_register(Fetcher())
    assert excinfo.value.code == "register_pending"
    assert excinfo.value.context["deadline"] == "2026-10-08"


def test_germany_publishes_no_register():
    assert GERMANY_PUBLISHES_REGISTER is False


def _listing(company: str = "Acme Robotics Ltd", description: str = "") -> JobListing:
    return JobListing(
        portal="greenhouse",
        external_id="1",
        title="Backend Engineer",
        company=company,
        location="London",
        url="https://jobs.example/1",
        description=description,
    )


def _register(*names: str) -> SponsorRegister:
    return SponsorRegister(
        country="GB",
        source_url="https://example.gov/register.csv",
        fetched_at="2026-10-04T00:00:00Z",
        names=frozenset(names),
        raw_count=len(names),
    )


def test_register_match_tags_but_never_drops():
    register = _register("acme robotics")
    tagged = badge(_listing(), register)
    assert tagged.visa_sponsorship is True

    # employer not in the register: still returned, tag untouched (None)
    other = badge(_listing(company="Gamma Industries"), register)
    assert other is not None
    assert other.visa_sponsorship is None
    assert other.company == "Gamma Industries"


def test_text_tagging_flags_advertised_sponsorship():
    advertised = _listing(description="We offer visa sponsorship for eligible candidates.")
    assert badge(advertised).visa_sponsorship is True
    plain = _listing(description="Competitive salary and pension.")
    assert badge(plain).visa_sponsorship is None
    # an already-known True is never downgraded by later passes
    pre_tagged = replace(_listing(description="no mention"), visa_sponsorship=True)
    assert badge(pre_tagged).visa_sponsorship is True


def test_normalize_employer_variants():
    assert normalize_employer("Acme Robotics Ltd") == normalize_employer("ACME ROBOTICS LIMITED")
    assert normalize_employer("Beta Health PLC") == "beta health"
    assert normalize_employer("") == ""


# ── all-country coverage (session 7 follow-up) ────────────────────────────


def _gb_fetcher() -> Fetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/register-of-licensed-sponsors-workers"):
            return httpx.Response(200, text=PAGE_HTML)
        return httpx.Response(200, text=CSV_BODY)

    return build(handler)


def test_every_country_of_interest_has_register_coverage():
    assert len(EUROPE) == 50
    codes = set(europe_iso2()) | {"AU"}
    assert len(codes) == 51
    statuses: set[str] = set()
    for code in sorted(codes):
        spec = register_spec(code)
        assert spec.iso2 == code
        assert spec.status in {REGISTER_PUBLISHED, REGISTER_PENDING, REGISTER_NONE}
        statuses.add(spec.status)
    # the three verified facts plus the country DB statuses
    assert statuses == {REGISTER_PUBLISHED, REGISTER_PENDING, REGISTER_NONE}


def test_fetch_register_dispatches_on_status():
    fetcher = _gb_fetcher()
    gb = fetch_register("GB", fetcher)
    assert gb.country == "GB"
    assert len(gb) == 2
    de = fetch_register("DE", fetcher)
    assert de.country == "DE"
    assert de.names == frozenset()
    assert de.raw_count == 0
    with pytest.raises(RegisterPending) as excinfo:
        fetch_register("AU", fetcher)
    assert excinfo.value.context["deadline"] == "2026-10-08"


def test_fetch_register_rejects_unknown_country():
    with pytest.raises(FetchError) as excinfo:
        fetch_register("ZZ", _gb_fetcher())
    assert excinfo.value.code == "register_country_unknown"


def test_fetch_registers_skips_pending_countries():
    registers = fetch_registers(["GB", "DE", "AU", "FR"], _gb_fetcher())
    assert [r.country for r in registers] == ["GB", "DE", "FR"]
    assert registers[1].names == frozenset()
    assert registers[2].names == frozenset()  # FR: no register published
