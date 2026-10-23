"""Non-European source coverage tests (tasks 15.13, 15.17).

Covers the CA/AU/NZ/US/GB/IE/DE/SE scope decision — **no Asian and no African
country ships** (task 15.17 removed Japan, the platform's only Asian
destination, and added the United States plus European destinations):
>=10 employers per visa source, the scholarship adapters, the seed into
the ingest store, and the country filters returning non-zero results.
"""



from engine.sources import ingest_store as store
from engine.sources.countries import (
    BY_ISO,
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


def test_world_scope_is_ca_au_nz_us_only():
    assert world_iso2() == frozenset({"CA", "AU", "NZ", "US"})


def test_no_asian_destination():
    # No Asian ISO2 code may leak into the world set (task 15.17 removed JP).
    asian = {"CN", "IN", "KR", "SG", "MY", "TH", "VN", "PH", "ID", "PK", "BD", "HK", "TW", "JP"}
    assert not (world_iso2() & asian)
    assert "JP" not in world_iso2()
    assert "JP" not in all_country_iso2()


def test_no_african_country():
    african = {"NG", "ZA", "KE", "EG", "GH", "MA", "ET", "TZ", "UG", "DZ"}
    assert not (world_iso2() & african)
    assert not (all_country_iso2() & african)


def test_eight_visa_countries_have_sponsor_registers():
    # BY_ISO includes European countries with sponsor registers; the four
    # non-European destinations plus GB/IE/DE/SE all have sponsor data.
    for iso in ("CA", "AU", "NZ", "US", "GB", "IE", "DE", "SE"):
        assert iso in BY_ISO, f"{iso} missing from BY_ISO"


def test_europe_default_unchanged():
    # search_targets() still returns only the 50 European countries.
    from engine.sources.countries import search_targets

    assert len(search_targets()) == 50


def test_world_targets_scoped():
    ranked = world_targets()
    assert {t.iso2 for t in ranked} == {"CA", "AU", "NZ", "US"}
    assert [t.iso2 for t in world_targets(iso2_filter={"CA", "US"})] == ["CA", "US"]


def test_eight_visa_sources_with_ten_plus_rows_each():
    assert len(VISA_SOURCES) == 8
    for source in VISA_SOURCES:
        assert len(source.employers) >= 10, f"{source.source_id} has <10 rows"


def test_scholarship_adapters_cover_eight_countries():
    countries = {s.country for s in SCHOLARSHIP_SOURCES}
    assert countries == {"CA", "AU", "NZ", "US", "GB", "IE", "DE", "SE"}
    assert len(SCHOLARSHIP_SOURCES) >= 14


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
    assert result["seeded"] == 96
    assert result["by_country"] == {
        "CA": 12, "AU": 12, "NZ": 12, "US": 12,
        "GB": 12, "IE": 12, "DE": 12, "SE": 12,
    }


def test_country_filters_return_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_INGEST_DIR", str(tmp_path / "ingest"))
    seed_visa_jobs()
    for country in ("CA", "AU", "NZ", "US", "GB", "IE", "DE", "SE"):
        jobs = store.search_jobs(country=country, verified_only=True)
        assert len(jobs) >= 10, f"{country} returned {len(jobs)}"
        assert all(j["country"] == country for j in jobs)
        assert all(j["visa_sponsorship"] for j in jobs)


def test_seed_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_INGEST_DIR", str(tmp_path / "ingest"))
    seed_visa_jobs()
    seed_visa_jobs()  # re-seed must not duplicate
    jobs = store.load_jobs()
    assert len(jobs) == 96


def test_source_summary_shape():
    summary = source_summary()
    assert summary["countries"] == ["AU", "CA", "DE", "GB", "IE", "NZ", "SE", "US"]
    assert summary["total_visa_rows"] == 96
    assert summary["total_scholarships"] == len(SCHOLARSHIP_SOURCES)
    assert len(summary["visa_sources"]) == 8
