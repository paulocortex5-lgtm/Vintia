"""End-to-end cover letter test (task 10.6).

Upload (workspace store) → parse → fetch posting → letter → schema-valid
payload persisted — every HTTP call served by ``httpx.MockTransport``.
Zero network, zero sleeps; the touched-host assertion pins the footprint.
"""

import json

import httpx
import pytest

from engine.errors import RobotsDisallowed
from engine.json_utils import load_json, validate
from engine.pipeline import run_cover_letter
from engine.sources.fetch import Fetcher
from engine.sources.ratelimit import DomainRateLimiter

JOB_URL = "https://job-boards.greenhouse.io/vaulttec/jobs/127817"
SCHEMA = load_json("engine/schemas/cover_letter.schema.json")

GREENHOUSE_JOB = {
    "id": 127817,
    "title": "Backend Engineer",
    "updated_at": "2026-09-14T10:55:28-05:00",
    "location": {"name": "London, United Kingdom"},
    "absolute_url": JOB_URL,
    "company_name": "Acme Robotics Ltd",
    "content": (
        "<p>Build Python services in London.</p>"
        "<ul><li>Python</li><li>Kubernetes</li><li>PostgreSQL</li></ul>"
    ),
}

RESUME_MD = """# Ada Okafor
Backend Engineer
Location: London, UK
ada@example.com | +44 20 1234 5678

## Skills
- Python, Kubernetes, PostgreSQL

## Experience
Backend Engineer, Acme (Jan 2021 - Present)
- Shipped the payments migration; cut p95 latency by 40%

## Education
BSc Computer Science, UNN (2020)

## Languages
English
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


def write_upload(tmp_path) -> None:
    ws = tmp_path / "ws7"
    ws.mkdir(exist_ok=True)
    (ws / "cv.md").write_text(RESUME_MD, encoding="utf-8")


def test_full_cover_letter_journey_offline_pinned_and_persisted(tmp_path):
    write_upload(tmp_path)
    fetcher, seen = make_fetcher(portal_handler)
    result = run_cover_letter(
        "ws7",
        "cv.md",
        JOB_URL,
        fetcher=fetcher,
        store_dir=str(tmp_path),
        run_id="run-14",
    )
    assert result["pipeline"] == {
        "task": "10.4",
        "workspace_id": "ws7",
        "resume_id": "cv.md",
        "job_url": JOB_URL,
        "run_id": "run-14",
    }
    payload = result["cover_letter"]
    validate(payload, SCHEMA)
    assert payload["resume_id"] == "cv.md" and payload["job_id"] == "127817"
    assert result["provider"] == "deterministic"

    # posting + resume facts only
    content = payload["content"]
    assert "Backend Engineer at Acme Robotics Ltd" in content
    assert "cut p95 latency by 40%" in content  # verbatim achievement
    assert "PostgreSQL" in content  # resume's own spelling of the keyword
    corpus = json.dumps(RESUME_MD) + json.dumps(GREENHOUSE_JOB)
    for number in __import__("re").findall(r"\d+", content):
        assert number in corpus, f"invented number in letter: {number}"

    # persisted next to the upload and round-trips
    persisted = tmp_path / "ws7" / "cv.md.cover.json"
    assert result["report_path"] == str(persisted)
    assert json.loads(persisted.read_text(encoding="utf-8")) == payload

    # touched-host pin: only the fixture's API origin, nothing else
    hosts = {httpx.URL(u).host for u in seen}
    assert hosts <= {"boards-api.greenhouse.io"}, hosts


def test_robots_disallow_refuses_the_letter(tmp_path):
    write_upload(tmp_path)
    fetcher, _seen = make_fetcher(
        portal_handler,
        robots_status=200,
        robots_body="User-agent: *\nDisallow: /\n",
    )
    with pytest.raises(RobotsDisallowed):
        run_cover_letter("ws7", "cv.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path))


def test_closed_listing_is_refused(tmp_path):
    write_upload(tmp_path)
    job = dict(GREENHOUSE_JOB, closes_at="2020-01-01")
    fetcher, _seen = make_fetcher(
        lambda request: (
            httpx.Response(200, json=job)
            if request.url.path == "/v1/boards/vaulttec/jobs/127817"
            else httpx.Response(404)
        )
    )
    from engine.errors import FetchError

    with pytest.raises(FetchError) as exc:
        run_cover_letter("ws7", "cv.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path))
    assert exc.value.code == "listing_inactive"
