"""Government jobs source tests — Federal Employment Agency DE (session 7).

Verified endpoint: ``rest.arbeitsagentur.de/.../pc/v4/app/jobs`` with the
public ``X-API-Key`` and app User-Agent (browser-style requests get 403).
All HTTP via MockTransport.
"""

import base64
from urllib.parse import quote

import httpx
import pytest

from engine.errors import FetchError
from engine.sources import FederalEmploymentAgency, Fetcher
from engine.sources.government import DEFAULT_API_KEY, SEARCH_URL
from engine.sources.ratelimit import DomainRateLimiter

AA_LIST = {
    "stellenangebote": [
        {
            "refnr": "123-45",
            "titel": "Data Engineer",
            "arbeitgeber": "ACME GmbH",
            "ort": "Berlin",
            "einstellungsdatum": "2026-09-20",
            "ablaufdatum": "2099-12-31",
            "url": "https://www.arbeitsagentur.de/jobsuche/job/123-45",
        },
        {
            "refnr": "999-1",
            "titel": "Expired Role",
            "arbeitgeber": "Old AG",
            "ort": "Köln",
            "einstellungsdatum": "2020-01-01",
            "ablaufdatum": "2020-02-01",
            "url": "",
        },
    ]
}

AA_DETAIL = {
    "refnr": "123-45",
    "stellenangebotsTitel": "Data Engineer",
    "arbeitgeber": "ACME GmbH",
    "ort": "Berlin",
    "gueltigBis": "2099-12-31",
    "aufgaben": "<p>Build data pipelines</p><script>x()</script>",
}


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


def test_search_hits_the_government_endpoint_with_required_headers():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["api_key"] = request.headers.get("x-api-key")
        seen["ua"] = request.headers.get("user-agent", "")
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=AA_LIST)

    source = FederalEmploymentAgency(build(handler))
    jobs = source.search("ingenieur", location="berlin", size=10)

    assert seen["path"] == "/jobboerse/jobsuche-service/pc/v4/app/jobs"
    assert seen["api_key"] == DEFAULT_API_KEY
    assert str(seen["ua"]).startswith("Jobsuche/")
    params = seen["params"]  # type: ignore[assignment]
    assert params["was"] == "ingenieur"
    assert params["wo"] == "berlin"
    assert params["size"] == "10"
    assert SEARCH_URL.endswith(str(seen["path"]))

    # only the live posting survives (ablaufdatum 2020 is dropped)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.portal == "de-arbeitsagentur"
    assert job.external_id == "123-45"
    assert job.title == "Data Engineer"
    assert job.company == "ACME GmbH"
    assert job.location == "Berlin"
    assert job.country == "DE"
    assert job.posted_at == "2026-09-20"
    assert job.closes_at == "2099-12-31"
    assert job.extra["refnr"] == "123-45"


def test_api_key_can_be_overridden():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("x-api-key", "")
        return httpx.Response(200, json={"stellenangebote": []})

    source = FederalEmploymentAgency(build(handler), api_key="custom-key")
    source.search("nurse")
    assert seen["key"] == "custom-key"


def test_load_uses_base64_refnr_in_the_path():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json=AA_DETAIL)

    source = FederalEmploymentAgency(build(handler))
    job = source.load("123-45")
    expected = "/jobboerse/jobsuche-service/pc/v4/jobdetails/" + quote(
        base64.b64encode(b"123-45").decode("ascii"), safe=""
    )
    assert seen["path"] == expected
    assert job.title == "Data Engineer"
    assert "Build data pipelines" in job.description
    assert "<p>" not in job.description and "x()" not in job.description
    assert job.closes_at == "2099-12-31"


def test_load_refuses_a_closed_posting():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**AA_DETAIL, "gueltigBis": "2020-01-01"})

    source = FederalEmploymentAgency(build(handler))
    with pytest.raises(FetchError) as excinfo:
        source.load("123-45")
    assert excinfo.value.code == "listing_inactive"


def test_gateway_rejection_surfaces_as_fetch_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden")

    source = FederalEmploymentAgency(build(handler))
    with pytest.raises(FetchError) as excinfo:
        source.search("anything")
    assert excinfo.value.context["status"] == 403


def test_non_json_response_is_a_fetch_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>maintenance</html>")

    source = FederalEmploymentAgency(build(handler))
    with pytest.raises(FetchError) as excinfo:
        source.search("anything")
    assert "non-JSON" in excinfo.value.message


def test_malformed_job_record_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"stellenangebote": ["not-a-dict"]})

    source = FederalEmploymentAgency(build(handler))
    with pytest.raises(FetchError):
        source.search("anything")
