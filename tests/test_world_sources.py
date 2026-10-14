"""Non-European source coverage tests (task 15.13 §17.4).

Covers the CA/AU/NZ/JP scope decision (Japan is the ONLY Asian
destination; no African country), >=10 employers per visa source, the
scholarship adapters, the seed into the ingest store, and the country
filters returning non-zero results.
"""

from datetime import UTC, datetime

import pytest

from engine.sources import ingest_store as store
from engine.sources.countries import (
    BY_ISO,
    WORLD_EXTRA,
    all_country_iso2,
    world_iso2,
    world_targets,
)
from engine.sources.world import (
    SCHOLARSHIP_SOURCES,
    VISA_SOURCES,
    seed_visa_jobs,
    source_summary,
)


def test_world_scope_is_ca_au_nz_jp_only():
    assert world_iso2() == frozenset({"CA", "AU", "NZ", "JP"})


def test_japan_is_the_only_asian_destination():
    # No other Asian ISO2 codes leak in beyond JP.
    asian = {"CN", "IN", "KR", "SG", "MY", "TH", "VN", "PH", "ID", "PK", "BD", "HK", "TW"}
    assert not (world_iso2() & asian)


def test_no_african_country():
    african = {"NG", "ZA", "KE", "EG", "GH", "MA", "ET", "TZ", "UG", "DZ"}
    assert not (world_iso2() & african)
    assert not (all_country_iso2() & african)


def test_four_countries_in_fast_lookup():
    for iso in ("CA", "AU", "NZ", "JP"):
        assert iso in BY_ISO
        assert BY_ISO[iso].sponsor_register == "published"


def test_europe_default_unchanged():
    # search_targets() still returns only the 50 European countries.
    from engine.sources.countries import search_targets

    assert len(search_targets()) == 50


def test_world_targets_scoped():
    ranked = world_targets()
    assert {t.iso2 for t in ranked} == {"CA", "AU", "NZ", "JP"}
    assert [t.iso2 for t in world_targets(iso2_filter={"CA", "JP"})] == ["CA", "JP"]


def test_four_visa_sources_with_ten_plus_rows_each():
    assert len(VISA_SOURCES) == 4
    for source in VISA_SOURCES:
        assert len(source.employers) >= 10, f"{source.source_id} has <10 rows"


def test_scholarship_adapters_cover_all_four_countries():
    countries = {s.country for s in SCHOLARSHIP_SOURCES}
    assert countries == {"CA", "AU", "NZ", "JP"}
    assert len(SCHOLARSHIP_SOURCES) >= 10


def test_every_row_cites_a_source():
    for source in VISA_SOURCES:
        assert source.url.startswith("https://")
        assert source.basis
    for sch in SCHOLARSHIP_SOURCES:
        assert sch.url.startswith("https://")
        assert sch.basis


def test_seed_populates_ingest_store(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_INGEST_DIR", str(tmp_path / "ingest"))
    result = seed_visa_jobs()
    assert result["seeded"] == 48
    assert result["by_country"] == {"CA": 12, "AU": 12, "NZ": 12, "JP": 12}


def test_country_filters_return_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_INGEST_DIR", str(tmp_path / "ingest"))
    seed_visa_jobs()
    for country in ("CA", "AU", "NZ", "JP"):
        jobs = store.search_jobs(country=country, verified_only=True)
        assert len(jobs) >= 10, f"{country} returned {len(jobs)}"
        assert all(j["country"] == country for j in jobs)
        assert all(j["visa_sponsorship"] for j in jobs)


def test_seed_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_INGEST_DIR", str(tmp_path / "ingest"))
    seed_visa_jobs()
    seed_visa_jobs()  # re-seed must not duplicate
    jobs = store.load_jobs()
    assert len(jobs) == 48


def test_source_summary_shape():
    summary = source_summary()
    assert summary["countries"] == ["AU", "CA", "JP", "NZ"]
    assert summary["total_visa_rows"] == 48
    assert summary["total_scholarships"] == len(SCHOLARSHIP_SOURCES)
    assert len(summary["visa_sources"]) == 4
