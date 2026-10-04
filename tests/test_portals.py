"""Portal-adapter tests: W/G/L parsing, URL claims, registry (task 2.2).

Payloads mirror the published portal APIs (Greenhouse Job Board API,
Lever Postings API, Workday CXS) and run against ``httpx.MockTransport``
— zero network I/O, zero real sleeps.
"""

import json

import httpx
import pytest

from engine.errors import FetchError, RobotsDisallowed
from engine.sources import Fetcher, adapter_for_url, adapters_for, load_listing
from engine.sources.portals import GreenhouseAdapter, LeverAdapter, WorkdayAdapter, strip_html
from engine.sources.portals.base import epoch_ms_date, iso_date
from engine.sources.ratelimit import DomainRateLimiter

# ── fixtures shaped like the real portals ─────────────────────────────

GREENHOUSE_JOB = {
    "id": 127817,
    "title": "Vault Designer",
    "updated_at": "2026-01-14T10:55:28-05:00",
    "location": {"name": "NYC"},
    "absolute_url": "https://job-boards.greenhouse.io/vaulttec/jobs/127817",
    "content": "Design vaults. &lt;p&gt;Bring &amp; shelter&lt;/p&gt;",
}

GREENHOUSE_LIST = {
    "jobs": [
        GREENHOUSE_JOB,
        {
            "id": 127818,
            "title": "Ops Engineer",
            "updated_at": "2026-02-01T09:00:00-05:00",
            "location": {"name": "Remote"},
            "absolute_url": "https://job-boards.greenhouse.io/vaulttec/jobs/127818",
            "content": "<p>Ship it</p><script>alert(1)</script>",
        },
    ]
}

LEVER_POSTING = {
    "id": "5ac21346-8e0c-4494-8e7a-3eb92ff77902",
    "text": "Senior Backend Engineer",
    "hostedUrl": "https://jobs.lever.co/leverdemo/5ac21346-8e0c-4494-8e7a-3eb92ff77902",
    "createdAt": 1754352000000,  # 2025-08-05T00:00:00Z
    "categories": {"location": "Berlin", "team": "Engineering", "commitment": "Full-time"},
    "descriptionPlain": "Build APIs.\nPython required.",
    "workplaceType": "hybrid",
}

WORKDAY_LIST = {
    "total": 2,
    "jobPostings": [
        {
            "title": "Sr. Software Engineer",
            "externalUrl": "https://acme.wd5.myworkdayjobs.com/en-US/ACME/job/Sr_Software_Engineer_R123",
            "postedOn": "Aug 5, 2026",
            "locationsText": "London, United Kingdom",
            "jobPostingId": "Sr_Software_Engineer_R123",
        },
        {
            "title": "Product Designer",
            "externalUrl": "https://acme.wd5.myworkdayjobs.com/en-US/ACME/job/Product_Designer_R124",
            "postedOn": "Aug 1, 2026",
            "locationsText": "Remote",
            "jobPostingId": "Product_Designer_R124",
        },
    ],
}

WORKDAY_DETAIL = {
    "jobPostingInfo": {
        "jobPostingId": "Sr_Software_Engineer_R123",
        "title": "Sr. Software Engineer",
        "postedOn": "Aug 5, 2026",
        "locationsText": "London, United Kingdom",
        "jobDescription": "<p>Build things</p><ul><li>Python</li></ul><script>x()</script>",
    }
}


def build(handler, *, robots_status: int = 404) -> Fetcher:
    """Fetcher over ``handler``; /robots.txt is answered by the wrapper."""

    def combined(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            if robots_status == 404:
                return httpx.Response(404)
            return httpx.Response(robots_status, text="User-agent: *\nDisallow: /v1/\n")
        return handler(request)

    limiter = DomainRateLimiter(min_interval_sec=0.0, max_per_day=10**6, sleep=lambda _s: None)
    return Fetcher(
        client=httpx.Client(transport=httpx.MockTransport(combined)),
        limiter=limiter,
        retries=1,
        sleep=lambda _s: None,
    )


def json_handler(payload: dict | list, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return handler


# ── Greenhouse ────────────────────────────────────────────────────────


def test_greenhouse_search_parses_jobs_and_strips_html():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["content_param"] = request.url.params.get("content", "")
        return httpx.Response(200, json=GREENHOUSE_LIST)

    adapter = GreenhouseAdapter(build(handler))
    jobs = adapter.search("vaulttec")
    assert seen["path"] == "/v1/boards/vaulttec/jobs"
    assert seen["content_param"] == "true"
    assert len(jobs) == 2

    first = jobs[0]
    assert first.portal == "greenhouse"
    assert first.external_id == "127817"
    assert first.title == "Vault Designer"
    assert first.company == "vaulttec"
    assert first.location == "NYC"
    assert first.posted_at == "2026-01-14"
    assert first.url.endswith("/vaulttec/jobs/127817")
    # entity-encoded HTML is decoded then stripped
    assert "Bring & shelter" in first.description
    assert "<p>" not in first.description
    # real tags stripped, <script> body dropped entirely
    assert jobs[1].description.strip() == "Ship it"
    assert "alert(1)" not in jobs[1].description


def test_greenhouse_search_honours_limit():
    adapter = GreenhouseAdapter(build(json_handler(GREENHOUSE_LIST)))
    assert len(adapter.search("vaulttec", limit=1)) == 1
    assert len(adapter.search("vaulttec", limit=25)) == 2


def test_greenhouse_load_fetches_the_single_job_endpoint():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json={**GREENHOUSE_JOB, "company_name": "Vault Tec"})

    adapter = GreenhouseAdapter(build(handler))
    job = adapter.load("https://job-boards.greenhouse.io/vaulttec/jobs/127817")
    assert seen["path"] == "/v1/boards/vaulttec/jobs/127817"
    assert job.company == "Vault Tec"  # detail payload overrides the token
    assert "Design vaults" in job.description


def test_greenhouse_missing_board_is_a_fetch_error():
    adapter = GreenhouseAdapter(build(json_handler({}, status=404)))
    with pytest.raises(FetchError) as excinfo:
        adapter.search("nope")
    assert excinfo.value.code == "fetch_error"
    assert excinfo.value.context["status"] == 404


def test_portals_respect_robots_disallow():
    adapter = GreenhouseAdapter(build(json_handler(GREENHOUSE_LIST), robots_status=200))
    with pytest.raises(RobotsDisallowed):
        adapter.search("vaulttec")


# ── Lever ─────────────────────────────────────────────────────────────


def test_lever_search_parses_categories_and_dates():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["query"] = str(request.url.query, "utf-8")
        return httpx.Response(200, json=[LEVER_POSTING])

    adapter = LeverAdapter(build(handler))
    jobs = adapter.search("leverdemo")
    assert seen["path"] == "/v0/postings/leverdemo"
    assert "mode=json" in seen["query"]
    assert len(jobs) == 1

    job = jobs[0]
    assert job.portal == "lever"
    assert job.external_id == LEVER_POSTING["id"]
    assert job.title == "Senior Backend Engineer"
    assert job.location == "Berlin"
    assert job.posted_at == "2025-08-05"  # createdAt epoch-ms → UTC date
    assert job.url == LEVER_POSTING["hostedUrl"]
    assert "Python required." in job.description
    assert job.extra["team"] == "Engineering"
    assert job.extra["commitment"] == "Full-time"
    assert job.extra["workplaceType"] == "hybrid"


def test_lever_load_uses_the_single_posting_endpoint():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json=LEVER_POSTING)

    adapter = LeverAdapter(build(handler))
    job = adapter.load("https://jobs.lever.co/leverdemo/5ac21346-8e0c-4494-8e7a-3eb92ff77902")
    assert seen["path"] == "/v0/postings/leverdemo/5ac21346-8e0c-4494-8e7a-3eb92ff77902"
    assert job.title == "Senior Backend Engineer"


# ── Workday ───────────────────────────────────────────────────────────


def test_workday_search_posts_to_the_cxs_endpoint():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["host"] = request.url.host
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=WORKDAY_LIST)

    adapter = WorkdayAdapter(build(handler))
    jobs = adapter.search("acme/ACME")
    assert seen["method"] == "POST"
    assert seen["host"] == "acme.wd5.myworkdayjobs.com"
    assert seen["path"] == "/wday/cxs/acme/ACME/jobs"
    assert seen["body"] == {"appliedFacets": {}, "limit": 25, "offset": 0, "searchText": ""}
    assert len(jobs) == 2

    first = jobs[0]
    assert first.portal == "workday"
    assert first.external_id == "Sr_Software_Engineer_R123"
    assert first.title == "Sr. Software Engineer"
    assert first.company == "acme"
    assert first.location == "London, United Kingdom"
    assert first.posted_at == "2026-08-05"
    assert first.url.startswith("https://acme.wd5.myworkdayjobs.com/")
    assert first.description == ""  # list endpoint omits it by design


def test_workday_load_posts_to_the_detail_endpoint():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json=WORKDAY_DETAIL)

    adapter = WorkdayAdapter(build(handler))
    url = "https://acme.wd5.myworkdayjobs.com/en-US/ACME/job/Sr_Software_Engineer_R123"
    job = adapter.load(url)
    assert seen["method"] == "POST"
    assert seen["path"] == "/wday/cxs/acme/ACME/job/Sr_Software_Engineer_R123"
    assert job.title == "Sr. Software Engineer"
    assert "Build things" in job.description
    assert "Python" in job.description
    assert "x()" not in job.description  # script dropped
    assert job.posted_at == "2026-08-05"


def test_workday_search_requires_tenant_site_source():
    adapter = WorkdayAdapter(build(json_handler(WORKDAY_LIST)))
    with pytest.raises(ValueError, match="tenant/site"):
        adapter.search("acme")


# ── registry + helpers ────────────────────────────────────────────────


def test_adapter_registry_claims_the_right_hosts():
    assert [a.name for a in adapters_for()] == ["greenhouse", "lever", "workday"]
    assert adapter_for_url("https://job-boards.greenhouse.io/x/jobs/1").name == "greenhouse"
    assert adapter_for_url("https://boards.greenhouse.io/x/jobs/1").name == "greenhouse"
    assert adapter_for_url("https://jobs.lever.co/x/uuid").name == "lever"
    assert adapter_for_url("https://jobs.eu.lever.co/x/uuid").name == "lever"
    assert adapter_for_url("https://acme.wd5.myworkdayjobs.com/en-US/A/job/x").name == "workday"
    assert adapter_for_url("https://example.com/jobs/1") is None


def test_load_listing_dispatches_by_host_and_rejects_unknown():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host or "")
        return httpx.Response(200, json={**GREENHOUSE_JOB, "company_name": "Vault Tec"})

    fetcher = build(handler)
    listing = load_listing("https://job-boards.greenhouse.io/vaulttec/jobs/127817", fetcher)
    assert listing.portal == "greenhouse"
    assert listing.title == "Vault Designer"

    with pytest.raises(FetchError) as excinfo:
        load_listing("https://example.com/jobs/1", fetcher)
    assert excinfo.value.code == "unsupported_portal"
    assert calls == ["boards-api.greenhouse.io"], "only the known host may hit the wire"


def test_strip_html_blocks_entities_and_skips_scripts():
    html = "<h1>Title</h1><p>A &amp; B</p><script>steal()</script><style>.x{}</style><br>done"
    text = strip_html(html)
    assert "Title" in text and "A & B" in text and "done" in text
    assert "steal()" not in text and ".x{}" not in text
    assert "<p>" not in text


def test_date_helpers_normalise_portal_formats():
    assert iso_date("2026-01-14T10:55:28-05:00") == "2026-01-14"
    assert iso_date("Aug 5, 2026") == "2026-08-05"
    assert iso_date("2026-08-01") == "2026-08-01"
    assert iso_date("sometime soon") is None
    assert iso_date(None) is None
    assert epoch_ms_date(1754352000000) == "2025-08-05"


# ── active-only policy (session 7) ────────────────────────────────────


def test_search_drops_expired_postings_and_load_refuses_them():
    expired = {**GREENHOUSE_JOB, "closes_at": "2000-01-01"}
    live = {**GREENHOUSE_JOB, "id": 999, "closes_at": "2999-12-31"}

    adapter = GreenhouseAdapter(build(json_handler({"jobs": [expired, live]})))
    jobs = adapter.search("vaulttec")
    assert [job.external_id for job in jobs] == ["999"], "closed postings must be dropped"

    # load() of a closed posting is refused outright
    closed = GreenhouseAdapter(build(json_handler(expired)))
    with pytest.raises(FetchError) as excinfo:
        closed.load("https://job-boards.greenhouse.io/vaulttec/jobs/127817")
    assert excinfo.value.code == "listing_inactive"


def test_is_active_defaults_to_true_without_a_closing_date():
    listing = GreenhouseAdapter(build(json_handler(GREENHOUSE_LIST))).search("vaulttec")[0]
    assert listing.closes_at is None
    assert listing.is_active()
    assert listing.visa_sponsorship is None  # tag starts unknown — never False
