"""European search database + targeting tests (product direction, session 7)."""

from dataclasses import replace

from engine.sources.countries import (
    BY_ISO,
    EUROPE,
    REGISTER_PUBLISHED,
    search_targets,
)

EU27 = {
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
}


def test_database_covers_all_european_countries():
    codes = {entry.iso2 for entry in EUROPE}
    assert len(EUROPE) == 50
    assert len(codes) == len(EUROPE), "ISO codes must be unique"
    assert EU27 <= codes, "every EU country must be listed"
    expected_extra = {
        "GB",
        "IS",
        "LI",
        "NO",
        "CH",  # UK + EFTA
        "AL",
        "BA",
        "XK",
        "ME",
        "MK",
        "RS",  # Western Balkans
        "UA",
        "BY",
        "MD",
        "RU",  # Eastern
        "GE",
        "AM",
        "AZ",
        "TR",  # Caucasus / transcontinental
        "AD",
        "MC",
        "SM",
        "VA",  # microstates
    }
    assert expected_extra <= codes


def test_every_entry_is_wellformed():
    for entry in EUROPE:
        assert len(entry.iso2) == 2
        assert entry.iso2 == entry.iso2.upper()
        assert entry.name
        assert entry.sponsor_register in {"published", "pending", "none"}
        assert entry.unemployment_rate is None or entry.unemployment_rate >= 0
        assert isinstance(entry.eu_eea, bool)


def test_only_verified_government_apis_are_registered():
    with_api = [entry.iso2 for entry in EUROPE if entry.gov_jobs_api]
    assert with_api == ["DE"], "only the verified Arbeitsagentur endpoint ships"
    assert "arbeitsagentur" in BY_ISO["DE"].gov_jobs_api


def test_uk_register_status_is_published():
    assert BY_ISO["GB"].sponsor_register == REGISTER_PUBLISHED
    assert "csv" in BY_ISO["GB"].notes.casefold()


def test_search_targets_ranks_and_pinpoints():
    ranked = search_targets()
    assert len(ranked) == 50
    scores = [entry.score() for entry in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0].iso2 == "DE", "machine-fetchable government API ranks first"

    # pinpoint to the countries the user picked (any subset, any order)
    picked = search_targets(iso2_filter={"pt", "es"})
    assert {entry.iso2 for entry in picked} == {"PT", "ES"}

    # structural pre-filters
    assert all(entry.eu_eea for entry in search_targets(eu_eea_only=True))
    assert all(entry.gov_jobs_api for entry in search_targets(with_api_only=True))

    # sponsorship must never gate the database: a country without a
    # register is still searchable, always
    assert len(search_targets(iso2_filter=None)) == 50


def test_unemployment_stats_refine_the_rank_when_populated():
    low = replace(BY_ISO["PT"], unemployment_rate=4.0)
    high = replace(BY_ISO["PT"], unemployment_rate=14.0)
    assert low.score() > high.score(), "less competition must rank higher"
    assert BY_ISO["PT"].unemployment_rate is None, "no unverified stats are embedded"


def test_lookup_helper():
    assert BY_ISO["DE"].name == "Germany"
    assert "DE" in {entry.iso2 for entry in EUROPE}
