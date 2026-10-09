"""run_ats_scan tests (task 9.5) — resolution order, guards, schema-valid report."""

import json

import httpx
import pytest

from engine.errors import FetchError, VantiaError
from engine.json_utils import load_json, validate
from engine.pipeline import run_ats_scan
from engine.sources.fetch import Fetcher
from engine.sources.ratelimit import DomainRateLimiter

JOB_URL = "https://job-boards.greenhouse.io/vaulttec/jobs/127817"
SCHEMA = load_json("engine/schemas/ats_score.schema.json")

GREENHOUSE_JOB = {
    "id": 127817,
    "title": "Backend Engineer",
    "updated_at": "2026-09-14T10:55:28-05:00",
    "location": {"name": "London, United Kingdom"},
    "absolute_url": JOB_URL,
    "company_name": "Acme Robotics Ltd",
    "content": (
        "<p>Build Python services in London.</p>"
        "<ul><li>Python</li><li>Kubernetes</li><li>5 years experience</li></ul>"
    ),
}

RESUME_MD = """# Ada Okafor
Backend Engineer
Location: London, UK
ada@example.com | +44 20 1234 5678

## Skills
- Python, Kubernetes

## Experience
Backend Engineer, Acme (Jan 2021 - Present)
- Shipped services; cut latency by 40%
"""


def make_fetcher(handler, *, robots_status: int = 404, robots_body: str = ""):
    """Fetcher over ``handler`` with a request log; /robots.txt routed by flag."""
    seen: list[str] = []

    def combined(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/robots.txt":
            if robots_status == 404:
                return httpx.Response(404)
            return httpx.Response(robots_status, text=robots_body)
        return handler(request)

    limiter = DomainRateLimiter(min_interval_sec=0.0, max_per_day=10**6, sleep=lambda _s: None)
    fetcher = Fetcher(
        client=httpx.Client(transport=httpx.MockTransport(combined)),
        limiter=limiter,
        retries=1,
        sleep=lambda _s: None,
    )
    return fetcher, seen


def portal_handler(job: dict | None = None):
    payload = job if job is not None else GREENHOUSE_JOB

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.url.host == "boards-api.greenhouse.io"
            and request.url.path == "/v1/boards/vaulttec/jobs/127817"
        ):
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    return handler


def write_upload(tmp_path, body: str = RESUME_MD, name: str = "cv.md") -> None:
    ws = tmp_path / "ws1"
    ws.mkdir(exist_ok=True)
    (ws / name).write_text(body, encoding="utf-8")


def test_scan_from_store_persists_a_schema_valid_report(tmp_path):
    write_upload(tmp_path)
    fetcher, _seen = make_fetcher(portal_handler())
    result = run_ats_scan("ws1", "cv.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path))

    assert result["pipeline"] == {
        "task": "9.5",
        "workspace_id": "ws1",
        "file_id": "cv.md",
        "job_url": JOB_URL,
        "run_id": "0",
    }
    report = result["report"]
    validate(report, SCHEMA)
    assert report["resume_id"] == "cv.md"
    assert report["job_id"] == "127817"
    assert result["job"]["portal"] == "greenhouse"
    assert result["parser"]["source_format"] == "md"
    persisted = str(tmp_path / "ws1" / "cv.md.ats.json")
    assert result["report_path"] == persisted
    with open(persisted, encoding="utf-8") as fh:
        assert json.load(fh) == report


def test_scan_with_explicit_profile_never_touches_the_store(tmp_path):
    fetcher, _seen = make_fetcher(portal_handler())
    result = run_ats_scan(
        "ws1",
        "missing.md",
        JOB_URL,
        resume={"name": "Ada", "title": "Backend Engineer", "skills": ["Python"]},
        fetcher=fetcher,
        store_dir=str(tmp_path / "does-not-exist"),
    )
    validate(result["report"], SCHEMA)
    assert result["report_path"] is None


def test_missing_upload_fails_before_any_network(tmp_path):
    def explode(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be touched for a bad upload")

    fetcher, seen = make_fetcher(explode)
    with pytest.raises(VantiaError) as exc:
        run_ats_scan("ws1", "nope.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path))
    assert exc.value.code == "profile_file_missing"
    assert seen == []  # nothing was requested, not even robots


def test_workspace_path_traversal_is_refused(tmp_path):
    def explode(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be touched for a bad workspace id")

    fetcher, _seen = make_fetcher(explode)
    with pytest.raises(VantiaError) as exc:
        run_ats_scan("..", "secrets.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path))
    assert exc.value.code == "workspace_path_invalid"
    with pytest.raises(VantiaError) as exc:
        run_ats_scan("ws1", "../../outside.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path))
    assert exc.value.code == "workspace_path_invalid"
    # a normalising-but-inside path is NOT a traversal — it resolves in-store
    with pytest.raises(VantiaError) as exc:
        run_ats_scan("ws1", "../sibling.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path))
    assert exc.value.code == "profile_file_missing"


def test_unparseable_upload_is_refused_before_any_network(tmp_path):
    write_upload(tmp_path, body="", name="empty.md")

    def explode(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be touched for a bad upload")

    fetcher, seen = make_fetcher(explode)
    with pytest.raises(VantiaError) as exc:
        run_ats_scan("ws1", "empty.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path))
    assert exc.value.code == "resume_parse_error"
    assert seen == []


def test_closed_listing_is_refused(tmp_path):
    write_upload(tmp_path)
    job = dict(GREENHOUSE_JOB, closes_at="2020-01-01")
    fetcher, _seen = make_fetcher(portal_handler(job))
    with pytest.raises(FetchError) as exc:
        run_ats_scan("ws1", "cv.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path))
    assert exc.value.code == "listing_inactive"


def test_unsupported_portal_is_refused(tmp_path):
    write_upload(tmp_path)
    fetcher, _seen = make_fetcher(portal_handler())
    with pytest.raises(FetchError) as exc:
        run_ats_scan(
            "ws1", "cv.md", "https://example.com/jobs/1", fetcher=fetcher, store_dir=str(tmp_path)
        )
    assert exc.value.code == "unsupported_portal"
