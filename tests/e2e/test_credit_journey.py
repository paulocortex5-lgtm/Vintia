"""End-to-end credit system test (task 11.6).

Free-user journey, fully offline: the balance API grants the monthly
allowance → a metered ATS scan and CV improvement spend it → the cover
letter is refused with R46 *before any network call* → a Paddle webhook
tops up exactly once under double delivery → the cover letter succeeds →
the estimate reports the real shortfall → the balance API's entries tell
the whole story. Every HTTP call is served by ``httpx.MockTransport`` and
the touched-host assertion pins the footprint to the fixture API host.
"""

import hashlib
import hmac
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from engine.credits import (
    default_ledger,
    reset_default_ledger,
    reset_default_meter,
)
from engine.credits.paddle_webhook import handle_webhook
from engine.errors import InsufficientCredits
from engine.pipeline import run_ats_scan, run_cover_letter, run_cv_improvement
from engine.sources.fetch import Fetcher
from engine.sources.ratelimit import DomainRateLimiter

JOB_URL = "https://job-boards.greenhouse.io/vaulttec/jobs/127817"
SECRET = "pwl_e2e_destination_secret"
USER = "user-e2e-1"

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


def make_fetcher(handler):
    """Fetcher over ``handler`` with a request log; /robots.txt 404s."""
    seen: list[str] = []

    def combined(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
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
    ws = tmp_path / "ws1"
    ws.mkdir(exist_ok=True)
    (ws / "cv.md").write_text(RESUME_MD, encoding="utf-8")


class _FakeSupabase:
    """In-memory stand-in for paddle_events idempotency lookups."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def query(self, table, filters, select="*", *, service=False):
        column = next(iter(filters))
        value = filters[column].split("=", 1)[-1]
        return [row for row in self.rows if row.get(column) == value]

    def upsert(self, table, rows, *, service=False):
        self.rows.extend(rows)
        return True


def paddle_event() -> bytes:
    return json.dumps(
        {
            "event_id": "evt_e2e_1",
            "event_type": "transaction.completed",
            "occurred_at": "2026-10-09T00:00:00Z",
            "custom_data": {"user_id": USER, "pack_id": "pack_10k", "credits": "10000"},
        }
    ).encode()


def sign(body: bytes) -> str:
    ts = str(int(time.time()))
    digest = hmac.new(SECRET.encode(), f"{ts}:{body.decode()}".encode(), hashlib.sha256).hexdigest()
    return f"ts={ts};h1={digest}"


@pytest.fixture()
def offline_env(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path / "credits"))
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", SECRET)
    reset_default_meter()  # meter binds the ledger at creation — drop it first
    reset_default_ledger()
    write_upload(tmp_path)
    yield tmp_path
    reset_default_meter()
    reset_default_ledger()


def test_full_credit_journey_offline(offline_env):
    tmp_path = offline_env
    seen: list[str] = []
    ledger = default_ledger()

    from engine.api import app

    with TestClient(app) as client:
        # 1. fresh free user sees this month's allowance (11.5 + 11.3)
        body = client.get("/credits/balance", params={"user_id": USER}).json()
        assert body["balance"] == 10_000
        assert body["tier"] == "free"
        assert body["operations"]["cv_scan"] == 2_000

        # 2. metered ATS scan: pre-flight before work, charge on completion
        fetcher, scan_seen = make_fetcher(portal_handler)
        scan = run_ats_scan(
            "ws1",
            "cv.md",
            JOB_URL,
            fetcher=fetcher,
            store_dir=str(tmp_path),
            run_id="r15",
            user_id=USER,
        )
        seen += scan_seen
        assert scan["credits"]["cost"] == 2_000
        assert scan["credits"]["balance_after"] == 8_000
        assert ledger.balance(USER) == 8_000

        # 3. metered CV improvement drains the rest of the allowance
        improve = run_cv_improvement(
            "ws1", "cv.md", store_dir=str(tmp_path), run_id="r15", user_id=USER
        )
        assert improve["credits"]["cost"] == 8_000
        assert ledger.balance(USER) == 0

        # 4. broke user: R46 refuses BEFORE any work (no fetch, no file)
        fetcher_refused, refused_seen = make_fetcher(portal_handler)
        with pytest.raises(InsufficientCredits) as excinfo:
            run_cover_letter(
                "ws1",
                "cv.md",
                JOB_URL,
                fetcher=fetcher_refused,
                store_dir=str(tmp_path),
                user_id=USER,
            )
        assert excinfo.value.context["balance"] == 0
        assert excinfo.value.context["required"] == 5_000
        assert refused_seen == []  # not a single network call happened
        assert not (tmp_path / "ws1" / "cv.md.cover.json").exists()

        # 5. Paddle webhook tops up — twice-delivered, credited once (R50)
        paddle = _FakeSupabase()  # one store: the idempotency lookup is its state
        first = handle_webhook(paddle_event(), sign(paddle_event()), supabase_client=paddle)
        assert first == {"status": "credited", "event_id": "evt_e2e_1", "ledger": "ok"}
        replay = handle_webhook(paddle_event(), sign(paddle_event()), supabase_client=paddle)
        assert replay["status"] == "already_processed"
        assert ledger.balance(USER) == 10_000  # exactly one top-up

        # 6. the cover letter now runs and charges 5 000
        fetcher_ok, cover_seen = make_fetcher(portal_handler)
        cover = run_cover_letter(
            "ws1",
            "cv.md",
            JOB_URL,
            fetcher=fetcher_ok,
            store_dir=str(tmp_path),
            run_id="r15",
            user_id=USER,
        )
        seen += cover_seen
        assert cover["credits"]["cost"] == 5_000
        assert cover["credits"]["balance_after"] == 5_000
        assert ledger.balance(USER) == 5_000

        # 7. estimate: honest shortfall, read-only (11.5)
        est = client.get(
            "/credits/estimate", params={"user_id": USER, "operation": "cv_improvement"}
        ).json()
        assert est["affordable"] is False
        assert est["balance"] == est["available"] == 5_000
        assert est["shortfall"] == 3_000

        # 8. the balance payload tells the whole story
        final = client.get("/credits/balance", params={"user_id": USER}).json()
        assert final["balance"] == 5_000
        assert final["entry_count"] == 5
        assert [e["kind"] for e in final["recent_entries"]] == [
            "grant",
            "spend",
            "spend",
            "topup",
            "spend",
        ]
        spend_refs = [e["ref"] for e in final["recent_entries"] if e["kind"] == "spend"]
        assert all(
            ref.startswith(("cv_scan:", "cv_improvement:", "cover_letter:")) for ref in spend_refs
        )

    # touched-host pin: only the fixture's API origin, nothing else
    hosts = {httpx.URL(u).host for u in seen}
    assert hosts <= {"boards-api.greenhouse.io"}, hosts
    assert seen  # the scans really fetched


def test_pipelines_without_user_id_stay_unmetered(offline_env):
    """No user_id → no meter, no ledger file, credits reported as None."""
    tmp_path = offline_env
    fetcher, _seen = make_fetcher(portal_handler)
    scan = run_ats_scan(
        "ws1", "cv.md", JOB_URL, fetcher=fetcher, store_dir=str(tmp_path), run_id="r0"
    )
    assert scan["credits"] is None
    assert not (tmp_path / "credits" / "ledger.json").exists()
    assert default_ledger().entries(USER) == []
