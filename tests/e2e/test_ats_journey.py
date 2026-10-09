"""End-to-end ATS scan test (task 9.6).

Upload (workspace store) → parse → fetch posting → twelve-point score →
schema-valid report persisted next to the file — every HTTP call served
by ``httpx.MockTransport``. Zero network, zero sleeps; the touched-host
assertion pins the footprint to the fixture host.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from engine.errors import RobotsDisallowed
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
        "<ul><li>Python</li><li>Kubernetes</li><li>PostgreSQL</li>"
        "<li>5 years experience</li></ul>"
    ),
}

RESUME_MD = """# Ada Okafor
Backend Engineer
Location: London, UK
ada@example.com | +44 20 1234 5678

## Summary
Backend engineer who shipped payments infra and cut latency by 40%.

## Skills
- Python, Kubernetes, PostgreSQL

## Experience
Backend Engineer, Acme (Jan 2021 - Present)
- Shipped the migration; cut p95 latency by 40%

## Education
BSc Computer Science, UNN (2020)
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


def portal_handler(request: httpx.Request) -> httpx.Response:
    if (
        request.url.host == "boards-api.greenhouse.io"
        and request.url.path == "/v1/boards/vaulttec/jobs/127817"
    ):
        return httpx.Response(200, json=GREENHOUSE_JOB)
    return httpx.Response(404)


def write_upload(tmp_path, body: str = RESUME_MD, name: str = "cv.md") -> str:
    ws = tmp_path / "ws42"
    ws.mkdir(exist_ok=True)
    path = ws / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_full_scan_journey_offline_pinned_and_persisted(tmp_path):
    write_upload(tmp_path)
    fetcher, seen = make_fetcher(portal_handler)
    result = run_ats_scan(
        "ws42", "cv.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path), run_id="run-13"
    )

    assert result["pipeline"]["task"] == "9.5"
    assert result["pipeline"]["run_id"] == "run-13"
    report = result["report"]
    validate(report, SCHEMA)

    # honest outputs: the posting's core stack matched, coverage is real
    assert {"python", "kubernetes", "postgresql"} <= {k.lower() for k in report["matched_keywords"]}
    assert 0.0 <= report["keyword_coverage"] <= 1.0
    assert 0.0 <= report["overall_score"] <= 100.0
    assert report["parser_metadata"]["source_format"] == "md"
    assert report["resume_id"] == "cv.md" and report["job_id"] == "127817"

    # the report persisted next to the upload and round-trips
    persisted = tmp_path / "ws42" / "cv.md.ats.json"
    assert persisted.exists()
    assert json.loads(persisted.read_text(encoding="utf-8")) == report

    # touched-host pin: only the fixture's API origin, nothing else
    hosts = {httpx.URL(u).host for u in seen}
    assert hosts <= {"boards-api.greenhouse.io"}, hosts


def test_robots_disallow_refuses_the_scan(tmp_path):
    write_upload(tmp_path)
    fetcher, _seen = make_fetcher(
        portal_handler, robots_status=200, robots_body="User-agent: *\nDisallow: /\n"
    )
    with pytest.raises(RobotsDisallowed):
        run_ats_scan("ws42", "cv.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path))


def test_api_scores_a_stored_upload_end_to_end(tmp_path, monkeypatch):
    """9.4 + 9.1 together: the API scores a workspace file by path."""
    path = write_upload(tmp_path)
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    with TestClient(__import__("engine.api", fromlist=["app"]).app) as client:
        response = client.post(
            "/ats/score",
            json={
                "resume": path,
                "job_title": "Backend Engineer",
                "job_description": "Python Kubernetes PostgreSQL. 5 years experience.",
                "job_location": "London",
                "resume_id": "ws42/cv.md",
            },
        )
    assert response.status_code == 200, response.text
    report = response.json()["report"]
    validate(report, SCHEMA)
    assert report["resume_id"] == "ws42/cv.md"
    assert {"python", "kubernetes"} <= {k.lower() for k in report["matched_keywords"]}
