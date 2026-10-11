"""End-to-end full journey test (task 7.1).

Visitor journey:
  1. Waitlist subscription and confirmation (task 5.6)
  2. ATS scan with scoring (task 9.5)
  3. CV improvement (task 10.2)
  4. Cover letter generation (task 10.4)
  5. Job application pipeline (task 2.8)

Every HTTP call is served by ``httpx.MockTransport``. Zero network, zero sleeps.
"""

import hashlib
import hmac
import json
import time
from uuid import uuid4

import httpx
import pytest

from engine.credits import (
    default_ledger,
    reset_default_ledger,
    reset_default_meter,
)
from engine.credits.paddle_webhook import handle_webhook
from engine.credits.tiers import ensure_allowance
from engine.json_utils import load_json, validate
from engine.pipeline import run_ats_scan, run_cover_letter, run_cv_improvement, run_job_pipeline
from engine.sources.fetch import Fetcher
from engine.sources.ratelimit import DomainRateLimiter
from engine.sources.registers import UK_PUBLICATION_URL
from engine.waitlist import WaitlistService, normalize_email

# ---- Test data -------------------------------------------------------------

JOB_URL = "https://job-boards.greenhouse.io/vaulttec/jobs/127817"

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

# UK sponsor-register fixture (same shape as test_job_pipeline.py) so the
# apply leg can prove the Acme Robotics Ltd badge instead of degrading.
PAGE_HTML = (
    '<html><body><a href="/csv-preview/abc123/Register_of_Worker_sponsors.csv">'
    "CSV , 10.4 MB</a></body></html>"
)
CSV_BODY = (
    "Organisation name,Rating,City,Worker categories\n"
    "Acme Robotics Ltd,A,London,Skilled Worker\n"
    "Beta Health PLC,B,Manchester,Charity\n"
)

# ---- Helper functions ------------------------------------------------------


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
        host, path = request.url.host, request.url.path
        if host == "boards-api.greenhouse.io":
            if path == "/v1/boards/vaulttec/jobs/127817":
                return httpx.Response(200, json=payload)
            return httpx.Response(404)
        if host == "www.gov.uk":
            # Sponsor register: publication page then the CSV it links to,
            # so run_job_pipeline can badge Acme Robotics Ltd (task 2.9).
            if path == UK_PUBLICATION_URL.split("www.gov.uk")[-1]:
                return httpx.Response(200, text=PAGE_HTML, headers={"content-type": "text/html"})
            if ".csv" in path or "/csv-preview/" in path:
                return httpx.Response(200, text=CSV_BODY, headers={"content-type": "text/csv"})
            return httpx.Response(404)
        return httpx.Response(404)

    return handler


def write_upload(tmp_path, body: str = RESUME_MD, name: str = "cv.md") -> str:
    ws = tmp_path / "ws42"
    ws.mkdir(exist_ok=True)
    path = ws / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def paddle_event() -> dict:
    return {
        "alert_id": "evt_e2e_1",
        "alert_name": "Underpayment",
        "currency": "GBP",
        "destination": {
            "account": {
                "account_type": "nullable:enum",
                "account_currency": "GBP",
                "entity_type": "nullable:enum",
                "id": "destination_e2e_1",
                "object": "bank_account",
            },
            "entity_type": "business",
            "id": "dest_e2e_1",
            "object": "destination",
            "address": {
                "city": "London",
                "country": "GB",
                "line1": "100 Example Street",
                "postal_code": "SW1A 1AA",
                "state": "Greater London",
            },
        },
        "event_type": "subscription_payment_succeeded",
        "height": 0,
        "invoice": {
            "currency": "GBP",
            "customer": "cus_e2e_1",
            "id": "inv_e2e_1",
            "object": "invoice",
        },
        "livemode": False,
        "metadata": {
            "vantia_user_id": "user-e2e-1",
            "vantia_operation": "topup",
            "vantia_amount": "10000",
        },
        "object": "alert",
        "paddle_sdk": "",
        "status": 200,
        "subscription": "sub_e2e_1",
        "user_id": "9876543210",
        "version": "2.0",
    }


def sign(event: dict) -> str:
    """Signature expected by ``handle_webhook`` for the test secret."""
    secret = "pwl_e2e_destination_secret"
    # Paddle signs "<timestamp>:<json_body>" with the secret.
    ts = str(int(time.time()))
    payload = json.dumps(event, separators=(",", ":")).encode()
    signed = f"{ts}:{payload.decode()}".encode()
    signature = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={signature}"


def top_up_via_paddle(
    user_id: str,
    amount: int = 10_000,
    supabase_client=None,
    *,
    event_id: str | None = None,
) -> dict:
    """Credit a balance through the real webhook path (signature + idempotency).

    Each purchase gets a unique ``event_id`` unless the caller passes one —
    redelivering the *same* event is how the journey proves R50 (at-least-once
    delivery must not double-credit).
    """
    event = paddle_event()
    event["event_type"] = "transaction.completed"
    event["custom_data"] = {
        "user_id": user_id,
        "credits": amount,
    }
    event["event_id"] = event_id or f"evt_{uuid4().hex}"
    event["occurred_at"] = "2025-01-01T00:00:00Z"  # fixed timestamp for testing
    raw_body = json.dumps(event, separators=(",", ":")).encode()
    signature = sign(event)
    return handle_webhook(raw_body, signature, supabase_client=supabase_client)


@pytest.fixture()
def offline_credits(tmp_path, monkeypatch):
    """Hermetic credit state — never the repo's persisted ``.vantia/credits`` store.

    The ledger is a real file (``$VANTIA_CREDITS_DIR/ledger.json``). Without
    this fixture a previous run's balances and idempotency refs leak into the
    next one: a re-used top-up event no-ops and the journey dies on R46.
    """
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path / "credits"))
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pwl_e2e_destination_secret")
    reset_default_meter()  # meter binds the ledger at creation — drop it first
    reset_default_ledger()


def test_full_journey_offline_pinned_and_persisted(tmp_path, offline_credits):
    """Run the complete visitor journey with credit metering and waitlist."""
    user_id = "user-e2e-1"

    # ------------------------------------------------- Waitlist ---------------
    email = "ada@example.com"
    normalized = normalize_email(email)

    # Use a fake Supabase client (same as in test_waitlist.py)
    class FakeSupabase:
        def __init__(self) -> None:
            self.rows: list[dict] = []
            self.events: list[dict] = []
            self.configured = True

        def query(self, table, filters, select="*", *, service=False):
            if table == "paddle_events":
                wanted = str(filters.get("event_id", ""))
                wanted = wanted.removeprefix("eq.")
                return [r for r in self.events if r.get("event_id") == wanted]
            if table != "waitlist":
                return []
            # Simple equality filter support for our tests.
            if "email" in filters and filters["email"].startswith("eq."):
                wanted = filters["email"][3:]
                matched = [r for r in self.rows if r.get("email") == wanted]
                if select == "*":
                    return matched
                return [{k: v for k, v in r.items() if k in select.split(",")} for r in matched]
            if "status" in filters and filters["status"].startswith("eq."):
                wanted = filters["status"][3:]
                matched = [r for r in self.rows if r.get("status") == wanted]
                if select == "*":
                    return matched
                return [{k: v for k, v in r.items() if k in select.split(",")} for r in matched]
            if "token_hash" in filters and filters["token_hash"].startswith("eq."):
                wanted = filters["token_hash"][3:]
                matched = [r for r in self.rows if r.get("token_hash") == wanted]
                if select == "*":
                    return matched
                return [{k: v for k, v in r.items() if k in select.split(",")} for r in matched]
            return []

        def upsert(self, table, rows, service=True):
            if table == "paddle_events":
                self.events.extend(rows)
                return
            if table != "waitlist":
                return
            for row in rows:
                existing = next((r for r in self.rows if r.get("email") == row.get("email")), None)
                if existing:
                    existing.update(row)
                else:
                    self.rows.append(row)

    # Instantiate waitlist service with our fake Supabase and a recording sender.

    class RecordingSender:
        def __init__(self) -> None:
            self.messages: list[dict] = []

        def send_confirmation(self, email: str, token: str) -> str:
            self.messages.append({"email": email, "token": token})
            return "outbox/message.json"

    supabase = FakeSupabase()
    sender = RecordingSender()
    waitlist = WaitlistService(supabase_client=supabase, sender=sender)

    # Ensure the user has enough credits for the three priced tasks.
    # The free monthly allowance lands exactly once (idempotent by month)…
    grant = ensure_allowance(user_id=user_id)
    assert grant["granted"] is True
    assert grant["tier"] == "free"
    # …and a sandbox top-up covers the rest (2 000 + 8 000 + 5 000 = 15 000),
    # delivered through the real webhook path (signature + event idempotency).
    first = top_up_via_paddle(user_id, amount=10_000, supabase_client=supabase)
    assert first["status"] == "credited"
    assert default_ledger().balance(user_id) == grant["amount"] + 10_000
    # R50: redelivery of the same event must move no credits.
    before = default_ledger().balance(user_id)
    replay = top_up_via_paddle(
        user_id, amount=10_000, supabase_client=supabase, event_id=first["event_id"]
    )
    assert replay["status"] == "already_processed"
    assert default_ledger().balance(user_id) == before

    # 1. Subscribe -> pending
    sub_result = waitlist.subscribe(normalized)
    assert sub_result["status"] == "pending"
    assert sub_result["confirmation_sent"] is True
    assert len(sender.messages) == 1
    token = sender.messages[0]["token"]  # the token sent in the outbox

    # 2. Confirm token -> confirmed
    conf_result = waitlist.confirm(token)
    assert conf_result["status"] == "confirmed"
    assert conf_result["already"] is False
    # Now the waitlist row should be confirmed.
    stats = waitlist.stats()
    assert stats["confirmed_count"] == 1
    assert stats["pending_count"] == 0

    # ------------------------------------------ ATS scan --------------------
    fetcher, seen = make_fetcher(portal_handler())
    write_upload(tmp_path)

    ats_result = run_ats_scan(
        "ws42",
        "cv.md",
        JOB_URL,
        fetcher=fetcher,
        store_dir=str(tmp_path),
        run_id="run-1",
        user_id=user_id,
    )

    assert ats_result["pipeline"]["task"] == "9.5"
    assert ats_result["pipeline"]["run_id"] == "run-1"
    report = ats_result["report"]
    # Load schema for validation
    SCHEMA_ATS = load_json("engine/schemas/ats_score.schema.json")
    validate(report, SCHEMA_ATS)
    assert report["resume_id"] == "ws42/cv.md"
    assert report["job_id"] == "127817"
    assert 0.0 <= report["overall_score"] <= 100.0

    # Credits charged
    assert "credits" in ats_result
    assert ats_result["credits"]["cost"] > 0
    assert ats_result["credits"]["balance_after"] >= 0

    # The report should persist next to the upload
    persisted = tmp_path / "ws42" / "cv.md.ats.json"
    assert persisted.exists()
    assert json.loads(persisted.read_text(encoding="utf-8")) == report

    # ---------------------------------------- CV improvement ----------------
    # Reuse the same resume (original) for improvement.
    improve_result = run_cv_improvement(
        "ws42",
        "cv.md",
        store_dir=str(tmp_path),
        job_description="Kubernetes Python experience",
        job_title="Backend Engineer",
        run_id="run-2",
        user_id=user_id,
    )

    assert improve_result["pipeline"]["task"] == "10.2"
    assert improve_result["pipeline"]["run_id"] == "run-2"
    improvement = improve_result["improvement"]
    SCHEMA_IMPROVE = load_json("engine/schemas/cv_improvement.schema.json")
    validate(improvement, SCHEMA_IMPROVE)
    assert improvement["original_cv_id"] == "ws42/cv.md"

    # Credits charged
    assert "credits" in improve_result
    assert improve_result["credits"]["cost"] > 0
    assert improve_result["credits"]["balance_after"] >= 0

    persisted_imp = tmp_path / "ws42" / "cv.md.improve.json"
    assert persisted_imp.exists()
    assert json.loads(persisted_imp.read_text(encoding="utf-8")) == improvement

    # ------------------------------------- Cover letter ---------------------
    # Use the improved resume as the base for the cover letter? Or original?
    # We'll use the original resume for simplicity; the improvement step is separate.
    cover_result = run_cover_letter(
        "ws42",
        "cv.md",
        JOB_URL,
        store_dir=str(tmp_path),
        run_id="run-3",
        user_id=user_id,
        fetcher=fetcher,
    )

    assert cover_result["pipeline"]["task"] == "10.4"
    assert cover_result["pipeline"]["run_id"] == "run-3"
    letter = cover_result["cover_letter"]
    SCHEMA_COVER = load_json("engine/schemas/cover_letter.schema.json")
    validate(letter, SCHEMA_COVER)
    assert letter["resume_id"] == "ws42/cv.md"
    assert letter["job_id"] == "127817"

    # Credits charged
    assert "credits" in cover_result
    assert cover_result["credits"]["cost"] > 0
    assert cover_result["credits"]["balance_after"] >= 0

    persisted_cov = tmp_path / "ws42" / "cv.md.cover.json"
    assert persisted_cov.exists()
    assert json.loads(persisted_cov.read_text(encoding="utf-8")) == letter

    # ------------------------------------- Job pipeline (apply) ------------
    # The job pipeline does not consume credits (task 2.8 is not priced).
    # We'll run it with the original resume to produce a tailored resume.
    job_result = run_job_pipeline(
        JOB_URL,
        write_upload(tmp_path, name="cv.md"),  # fresh upload
        "GB",
        fetcher=fetcher,
    )

    assert job_result["resume"]["provider"] == "deterministic"
    assert job_result["sponsorship"]["matched"] is True  # Acme Robotics Ltd is in the UK register
    assert job_result["fraud"]["verdict"] == "clean"
    # The pipeline should have generated a resume
    assert "resume" in job_result
    assert job_result["resume"]["matched_keywords"]  # at least some keywords matched

    # ------------------------------------- Host pinning ---------------------
    # Ensure only the fixture hosts were contacted (portal + sponsor register).
    hosts = {httpx.URL(u).host for u in seen}
    assert hosts <= {"boards-api.greenhouse.io", "www.gov.uk"}, f"Unexpected hosts: {hosts}"

    # ------------------------------------- Final state ----------------------
    # Optionally, we could check that the waitlist service still shows confirmed.
    final_stats = waitlist.stats()
    assert final_stats["confirmed_count"] == 1
    assert final_stats["pending_count"] == 0


if __name__ == "__main__":
    # Allow running the test directly for debugging.
    pytest.main([__file__, "-v"])
