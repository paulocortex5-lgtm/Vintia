"""Credential-equivalence tests (task 2.4) — offline, no network."""

import httpx
import pytest

from engine.credentials import (
    CREDENTIALS,
    ECTS_GRADES,
    degree_in_country,
    describe,
    equivalence,
    gpa_to_ects,
    lookup,
    remote_lookup,
)
from engine.errors import FetchError, VantiaError
from engine.sources.fetch import Fetcher
from engine.sources.ratelimit import DomainRateLimiter


def build(handler) -> Fetcher:
    limiter = DomainRateLimiter(min_interval_sec=0.0, max_per_day=10**6, sleep=lambda _s: None)
    return Fetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        limiter=limiter,
        retries=1,
        sleep=lambda _s: None,
    )


# ── registry integrity ─────────────────────────────────────────────────


def test_registry_rows_are_unique_and_sourced():
    ids = [row.id for row in CREDENTIALS]
    assert len(ids) == len(set(ids))
    for row in CREDENTIALS:
        assert row.basis, f"{row.id} must document where its facts come from"
        assert row.country in {"GB", "FR", "DE", "NG", "INT"}
        assert row.cycle in {
            "secondary",
            "vocational",
            "sub_degree",
            "bachelor",
            "master",
            "doctorate",
        }
        if row.eqf_level is not None:
            assert 1 <= row.eqf_level <= 8
        if row.ects is not None:
            assert row.ects > 0


def test_readme_headline_queries_resolve():
    # the README promise: NVQ, HND, BTS, CAP ↔ ECTS
    assert describe("NVQ Level 3").id == "gb-nvq-3"
    hnd = describe("HND")
    assert hnd.id == "gb-hnd" and hnd.ects == 120 and hnd.eqf_level == 5
    bts = describe("BTS")
    assert bts.country == "FR" and bts.ects == 120 and bts.eqf_level == 5
    assert describe("CAP").id == "fr-cap"


def test_accents_and_casefold_do_not_block_matches():
    assert describe("Baccalauréat").id == "fr-bac"
    assert describe("BACCALAUREAT").id == "fr-bac"
    assert describe("  hnd  ").id == "gb-hnd"


def test_country_filter_splits_the_two_hnds():
    assert describe("higher national diploma").id == "gb-hnd"
    assert describe("higher national diploma", country="NG").id == "ng-hnd"


def test_unqualified_degree_query_prefers_the_bologna_row():
    assert [row.id for row in lookup("master")][:2] == ["int-master", "fr-master"]
    assert describe("bachelor of science").id == "int-bachelor"
    assert describe("btech").id == "int-bachelor-4yr"


def test_unknown_query_returns_none_not_a_guess():
    result = equivalence("mystery degree")
    assert result["match"] is None
    assert result["target_title"] is None
    assert "enic-naric" in result["advice"]


def test_unverified_crosswalk_advises_recognition_check():
    result = equivalence("A level", target_country="DE")
    assert result["match"]["eqf_level"] is None  # honest gap, not a fabricated number
    assert "enic-naric" in result["advice"]
    assert result["target_title"] is None


def test_equivalence_places_a_bachelor_in_the_target_country():
    result = equivalence("hnd", country="GB", target_country="DE")
    assert result["match"]["eqf_level"] == 5
    assert result["target_title"]  # level-5 title in Germany
    result = equivalence("bachelor", target_country="FR")
    assert result["target_title"] == "Licence"


def test_degree_in_country_bounds():
    assert degree_in_country(6, "AU") == "Bachelor degree (AQF level 7)"
    assert degree_in_country(7, "XX") == "master's degree or equivalent"  # generic fallback
    assert degree_in_country(3, "DE") is None  # below degree level
    assert degree_in_country(None, "DE") is None
    assert degree_in_country(6, "") is None


# ── GPA ↔ ECTS ─────────────────────────────────────────────────────────


def test_gpa_bands_on_a_four_point_scale():
    assert gpa_to_ects(4.0).code == "A"
    assert gpa_to_ects(3.6).code == "A"  # 0.90 boundary
    assert gpa_to_ects(3.2).code == "B"
    assert gpa_to_ects(2.8).code == "C"
    assert gpa_to_ects(2.4).code == "D"
    assert gpa_to_ects(2.0).code == "E"
    assert gpa_to_ects(0.0).code == "F"
    assert ECTS_GRADES[-1].code == "F"


def test_gpa_respects_other_scales_and_validates():
    assert gpa_to_ects(9.0, scale=10.0).code == "A"
    assert gpa_to_ects(85.0, scale=100.0).code == "B"  # 0.85 ratio
    assert gpa_to_ects(72.0, scale=100.0).code == "C"  # 0.72 ratio


# ── optional remote lookup ─────────────────────────────────────────────


def test_remote_lookup_refuses_when_unconfigured(monkeypatch):
    monkeypatch.delenv("VANTIA_EQUIVALENCE_ENDPOINT", raising=False)
    with pytest.raises(VantiaError) as excinfo:
        remote_lookup("hnd")
    assert excinfo.value.code == "equivalence_endpoint_unconfigured"


def test_remote_lookup_parses_results_through_fetcher(monkeypatch):
    monkeypatch.delenv("VANTIA_EQUIVALENCE_ENDPOINT", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "hnd"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Remote Credential",
                        "country": "PT",
                        "eqf_level": "6",
                        "ects": "180",
                        "aliases": ["rc"],
                    }
                ]
            },
        )

    rows = remote_lookup("hnd", fetcher=build(handler), endpoint="https://registry.example/lookup")
    assert len(rows) == 1
    row = rows[0]
    assert row.title == "Remote Credential"
    assert row.country == "PT"
    assert row.eqf_level == 6 and row.ects == 180
    assert row.aliases == ("rc",)
    assert "registry.example" in row.basis


def test_remote_lookup_rejects_bad_payloads():
    def not_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    with pytest.raises(FetchError) as excinfo:
        remote_lookup("x", fetcher=build(not_json), endpoint="https://registry.example/lookup")
    assert excinfo.value.code == "equivalence_bad_payload"

    def wrong_shape(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"oops": []})

    with pytest.raises(FetchError) as excinfo:
        remote_lookup("x", fetcher=build(wrong_shape), endpoint="https://registry.example/lookup")
    assert excinfo.value.code == "equivalence_bad_payload"

    def missing_title(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"country": "PT"}]})

    with pytest.raises(FetchError) as excinfo:
        remote_lookup("x", fetcher=build(missing_title), endpoint="https://r.example/l")
    assert excinfo.value.code == "equivalence_bad_payload"

    with pytest.raises(VantiaError) as excinfo:
        gpa_to_ects(5.0, scale=4.0)
    assert excinfo.value.code == "grade_out_of_range"
    with pytest.raises(VantiaError) as excinfo:
        gpa_to_ects(1.0, scale=0)
    assert excinfo.value.code == "grade_scale_invalid"
