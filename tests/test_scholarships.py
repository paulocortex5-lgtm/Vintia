"""Scholarship engine tests — tasks 3.1 (database), 3.4 (mapper), 3.5 (windows).

Windows are asserted against injected dates, including the boundary
days (day before open, open day, close day, day after close) and the
year-wrapping Erasmus Mundus cycle. No network anywhere.
"""

from dataclasses import replace
from datetime import date

import pytest

from engine.errors import VantiaError
from engine.scholarships import (
    EUROPEAN_PROGRAMME_COUNTRIES,
    SCHOLARSHIPS,
    get_scholarship,
    map_credential,
    open_windows,
    search_scholarships,
    window_status,
    windows,
)

VERIFIED_ON = "2026-10-06"
OFFICIAL_HOSTS = (
    "www.chevening.org",
    "cscuk.fcdo.gov.uk",
    "www.daad.de",
    "erasmus-plus.ec.europa.eu",
    "www.dfat.gov.au",
)


# ── 3.1 database ───────────────────────────────────────────────────────


def test_database_has_five_sourced_programs():
    assert len(SCHOLARSHIPS) == 5
    ids = [row.id for row in SCHOLARSHIPS]
    assert len(ids) == len(set(ids))
    for row in SCHOLARSHIPS:
        assert row.basis, f"{row.id} must document its provenance"
        assert VERIFIED_ON in row.basis, f"{row.id} provenance must carry the check date"
        assert row.url.startswith("https://")
        assert any(host in row.url for host in OFFICIAL_HOSTS)
        assert row.funding in {"fully_funded", "varies"}
        assert 6 <= row.min_eqf_level <= 8
        assert row.fields and row.level in {"masters", "phd", "any"}


def test_get_scholarship_roundtrip_and_not_found():
    assert get_scholarship("chevening").name == "Chevening Scholarship"
    with pytest.raises(VantiaError) as excinfo:
        get_scholarship("nope")
    assert excinfo.value.code == "scholarship_not_found"


def test_search_filters_host_nationality_and_funding():
    assert {s.id for s in search_scholarships(host_country="DE")} == {"daad", "erasmus-mundus"}
    assert [s.id for s in search_scholarships(host_country="SE")] == ["erasmus-mundus"]
    assert [s.id for s in search_scholarships(host_country="AU")] == ["australia-awards"]
    ph = {s.id for s in search_scholarships(nationality="PH")}
    assert "commonwealth-uk" not in ph and "chevening" in ph
    ng = {s.id for s in search_scholarships(nationality="NG")}
    assert "commonwealth-uk" in ng
    assert [s.id for s in search_scholarships(funding="varies")] == ["daad"]
    assert len(search_scholarships(level="masters")) == 5  # "any" rows pass every level


def test_spans_europe_only_for_erasmus_mundus():
    emjm = get_scholarship("erasmus-mundus")
    assert emjm.spans_europe
    assert not any(s.spans_europe for s in SCHOLARSHIPS if s.id != "erasmus-mundus")
    assert set(emjm.host_countries) == EUROPEAN_PROGRAMME_COUNTRIES


# ── 3.4 credential mapper ──────────────────────────────────────────────


def test_mapper_accepts_a_bachelors_equivalent():
    result = map_credential("erasmus-mundus", "bachelor of science")
    assert result["meets_level"] is True
    assert result["required_eqf_level"] == 6
    assert result["credential"]["eqf_level"] == 6
    assert "meets the entry level" in result["advice"]


def test_mapper_rejects_a_sub_bachelor_credential():
    result = map_credential("erasmus-mundus", "HND")
    assert result["meets_level"] is False
    assert "falls short" in result["advice"]


def test_mapper_stays_silent_when_the_level_is_unverified():
    result = map_credential("erasmus-mundus", "A level")
    assert result["meets_level"] is None  # no fabricated verdict
    assert "enic-naric" in result["advice"].lower()


def test_mapper_handles_unknown_credentials_and_programs():
    result = map_credential("daad", "mystery degree")
    assert result["credential"] is None and result["meets_level"] is None
    with pytest.raises(VantiaError) as excinfo:
        map_credential("nope", "HND")
    assert excinfo.value.code == "scholarship_not_found"


def test_mapper_honours_the_issuing_country_filter():
    ng = map_credential("daad", "higher national diploma", country="NG")
    gb = map_credential("daad", "higher national diploma", country="GB")
    assert ng["credential"]["id"] == "ng-hnd"  # no verified EQF → None verdict
    assert ng["meets_level"] is None
    assert gb["credential"]["id"] == "gb-hnd"
    assert gb["meets_level"] is False  # EQF 5 < 6


# ── 3.5 window tracker ─────────────────────────────────────────────────


def test_chevening_window_boundaries():
    def status(day: date) -> str:
        return str(window_status(get_scholarship("chevening"), day)["status"])

    assert status(date(2026, 7, 31)) == "upcoming"  # day before open
    assert status(date(2026, 8, 1)) == "open"  # open day
    assert status(date(2026, 10, 6)) == "open"
    assert status(date(2026, 10, 31)) == "open"  # close day (inclusive)
    assert status(date(2026, 11, 1)) == "closed"  # day after close
    assert status(date(2027, 2, 1)) == "closed"  # closer to close than to open
    assert status(date(2027, 7, 1)) == "upcoming"  # closer to next open


def test_erasmus_mundus_wraps_the_year():
    def status(day: date) -> str:
        return str(window_status(get_scholarship("erasmus-mundus"), day)["status"])

    assert status(date(2026, 9, 30)) == "upcoming"
    assert status(date(2026, 10, 1)) == "open"
    assert status(date(2026, 12, 15)) == "open"  # window spans new year
    assert status(date(2027, 1, 31)) == "open"
    assert status(date(2027, 2, 1)) == "closed"
    assert status(date(2026, 2, 15)) == "closed"  # closer to the finished close
    assert status(date(2026, 9, 15)) == "upcoming"  # closer to the next open


def test_open_days_and_counts_are_concrete():
    on = window_status(get_scholarship("chevening"), date(2026, 10, 6))
    assert on["opens"] == "2026-08-01" and on["closes"] == "2026-10-31"
    assert on["days_left"] == 25
    assert on["precision"] == "month"
    closed = window_status(get_scholarship("chevening"), date(2026, 11, 1))
    assert closed["next_opens"] == "2027-08-01"
    upcoming = window_status(get_scholarship("erasmus-mundus"), date(2026, 9, 15))
    assert upcoming["opens"] == "2026-10-01" and upcoming["days_until_open"] == 16


def test_programs_without_an_embedded_window_say_unknown():
    for sid in ("daad", "commonwealth-uk", "australia-awards"):
        row = window_status(get_scholarship(sid), date(2026, 10, 6))
        assert row["status"] == "unknown"
        assert "official page" in row["note"]
        assert row["opens"] is None and row["days_left"] is None


def test_windows_and_open_windows_lists():
    statuses = windows(date(2026, 10, 6))
    assert [w["id"] for w in statuses] == [s.id for s in SCHOLARSHIPS]
    assert [w["id"] for w in open_windows(date(2026, 10, 6))] == [
        "chevening",
        "erasmus-mundus",
    ]
    assert open_windows(date(2027, 5, 1)) == []


def test_fixed_non_annual_window_never_reruns():
    fixed = replace(
        get_scholarship("chevening"),
        annual=False,
        window_open="2026-01-15",
        window_close="2026-02-15",
    )
    assert window_status(fixed, date(2026, 1, 10))["status"] == "upcoming"
    assert window_status(fixed, date(2026, 1, 20))["days_left"] == 26
    after = window_status(fixed, date(2027, 3, 1))
    assert after["status"] == "closed"
    assert after["next_opens"] is None  # one-shot window has no rerun
