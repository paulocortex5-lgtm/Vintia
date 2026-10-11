"""Full user journey through the deployed HTTP surface (task 13.6).

One script-walk through every step a real user takes, served entirely by
the FastAPI app with zero network:

  1. Visitor: ``GET /health`` + ``GET /status``
  2. Waitlist: subscribe → double opt-in confirm (fake table, real flow)
  3. Auth: a Supabase-shaped HS256 JWT is minted and *verified offline*
     by ``engine.auth.require_user`` — the same check the deployed
     credentialed routes perform
  4. Workspace tools: ATS upload scan, paste-path parity, CV improvement,
     cover letter — each schema-valid
  5. Credits: free allowance granted, estimate, Paddle checkout (stubbed
     client), webhook top-up through the real HMAC path (at-least-once
     delivery must not double-credit), then the monthly statement
  6. Static UI wiring: the browser pages exist and call exactly these
     engine routes, and the utility pages stay out of the sitemap
"""

import hashlib
import hmac
import json
import time
from pathlib import Path
from uuid import uuid4

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from engine.credits import reset_default_ledger, reset_default_meter
from engine.errors import AuthError
from engine.json_utils import load_json, validate
from engine.waitlist import WaitlistService

ATS_SCHEMA = load_json("engine/schemas/ats_score.schema.json")
IMPROVE_SCHEMA = load_json("engine/schemas/cv_improvement.schema.json")
COVER_SCHEMA = load_json("engine/schemas/cover_letter.schema.json")

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

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

JD = "Backend Engineer. Python Kubernetes PostgreSQL. 3 years experience."

WEBHOOK_SECRET = "pwl_journey_secret"


# ── offline fakes (same shapes as tests/test_waitlist.py) ─────────────


class FakeSupabase:
    """In-memory waitlist table honoring the eq.-filter convention."""

    configured = True

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def query(self, table, filters, select="*", *, service=False):
        column, raw_filter = next(iter(filters.items()))
        raw = raw_filter.partition("eq.")[2]
        return [dict(r) for r in self.rows if str(r.get(column)) == raw]

    def upsert(self, table, rows, *, service=False):
        for row in rows:
            self.rows = [r for r in self.rows if r["email"] != row["email"]]
            self.rows.append(dict(row))
        return True


class RecordingSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_confirmation(self, email, token):
        self.sent.append((email, token))
        return "recording://sent"


def mint_supabase_jwt(user_id: str, secret: str) -> str:
    """A token shaped exactly like Supabase Auth issues (HS256, aud, sub)."""
    now = int(time.time())
    return pyjwt.encode(
        {
            "sub": user_id,
            "role": "authenticated",
            "aud": "authenticated",
            "exp": now + 3600,
            "iat": now,
        },
        secret,
        algorithm="HS256",
    )


def paddle_webhook_body(user_id: str, credits: int, event_id: str) -> tuple[bytes, str]:
    """Signed webhook body + signature — the real Paddle HMAC contract."""
    event = {
        "alert_id": "evt_journey_1",
        "alert_name": "Notification",
        "event_type": "transaction.completed",
        "event_id": event_id,
        "occurred_at": "2025-01-01T00:00:00Z",
        "livemode": False,
        "status": 200,
        "custom_data": {"user_id": user_id, "credits": credits},
    }
    payload = json.dumps(event, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    signature = hmac.new(
        WEBHOOK_SECRET.encode(), f"{ts}:{payload.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    return payload, f"ts={ts};h1={signature}"


@pytest.fixture()
def journey(monkeypatch, tmp_path):
    """Hermetic engine: isolated credits store, fake waitlist, stubbed Paddle."""
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path / "credits"))
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "journey-jwt-secret-not-a-real-one")
    reset_default_ledger()
    reset_default_meter()

    fake = WaitlistService(supabase_client=FakeSupabase(), sender=RecordingSender())
    monkeypatch.setattr("engine.api._waitlist_service", lambda: fake)
    monkeypatch.setattr(
        "engine.api.create_checkout_transaction",
        lambda user_id, pack_id: f"https://sandbox.paddle.com/checkout/{pack_id}",
    )
    from engine.api import app

    with TestClient(app) as client:
        yield client, fake


def test_full_user_journey_offline(journey):
    client, waitlist = journey

    # 1. Visitor lands and reads honest build state.
    assert client.get("/health").json()["status"] == "ok"
    status = client.get("/status").json()
    assert status["initialised"] is True and status["total"] == 88

    # 2. Waitlist double opt-in — pending until the emailed token is redeemed.
    subscribed = client.post("/waitlist/subscribe", json={"email": "ada@example.com"}).json()
    assert subscribed["status"] == "pending" and subscribed["confirmation_sent"] is True
    token = waitlist.sender.sent[0][1]
    assert token not in json.dumps(subscribed)  # response never leaks the token
    confirmed = client.post("/waitlist/confirm", json={"token": token}).json()
    assert confirmed["status"] == "confirmed"
    assert client.get("/waitlist/stats").json()["confirmed_count"] == 1

    # 3. Auth: the deployed UI stores a Supabase session; the engine verifies
    #    it offline against SUPABASE_JWT_SECRET (HS256 pinned).
    from engine.auth import require_user

    user_id = str(uuid4())
    access_token = mint_supabase_jwt(user_id, "journey-jwt-secret-not-a-real-one")
    context = require_user(f"Bearer {access_token}")
    assert context.user_id == user_id and context.role == "authenticated"
    with pytest.raises(AuthError):
        require_user("Bearer not.a.token")

    # 4. Workspace tools — upload path, paste parity, improve, cover letter.
    uploaded = client.post(
        "/ats/upload",
        files={"file": ("cv.md", RESUME_MD.encode("utf-8"), "text/markdown")},
        data={"job_description": JD},
    )
    assert uploaded.status_code == 200, uploaded.text
    report = uploaded.json()["report"]
    validate(report, ATS_SCHEMA)
    assert len(report["category_scores"]) == 12

    pasted = client.post(
        "/ats/score", json={"resume_text": RESUME_MD, "job_description": JD}
    ).json()["report"]
    assert pasted["overall_score"] == report["overall_score"]  # parity, both paths

    improved = client.post(
        "/improve/cv", json={"resume_text": RESUME_MD, "resume_id": "journey-cv"}
    )
    assert improved.status_code == 200, improved.text
    improvement = improved.json()["improvement"]
    validate(improvement, IMPROVE_SCHEMA)
    assert improvement["original_cv_id"] == "journey-cv"

    letter = client.post(
        "/cover/letter",
        json={
            "resume_text": RESUME_MD,
            "job_title": "Backend Engineer",
            "company": "Acme Robotics Ltd",
            "job_description": JD,
        },
    )
    assert letter.status_code == 200, letter.text
    cover = letter.json()["cover_letter"]
    validate(cover, COVER_SCHEMA)
    assert cover["job_id"].startswith("manual-")

    # 5. Credits: free allowance, estimate, checkout, webhook top-up, statement.
    balance = client.get("/credits/balance", params={"user_id": user_id}).json()
    assert balance["allowance"]["granted"] is True
    free_balance = balance["balance"]
    assert free_balance == balance["monthly_allowance"]

    estimate = client.get(
        "/credits/estimate", params={"user_id": user_id, "operation": "cv_scan"}
    ).json()
    assert estimate["cost"] > 0 and estimate["affordable"] is True

    checkout = client.post("/credits/checkout", json={"user_id": user_id, "pack_id": "pack_10k"})
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["checkout_url"].startswith("https://sandbox.paddle.com/")

    event_id = f"evt_{uuid4().hex}"
    body, signature = paddle_webhook_body(user_id, 10_000, event_id)
    applied = client.post("/paddle/webhook", content=body, headers={"Paddle-Signature": signature})
    assert applied.status_code == 200, applied.text

    # At-least-once delivery: redelivering the same event must not double-credit.
    replay = client.post("/paddle/webhook", content=body, headers={"Paddle-Signature": signature})
    assert replay.status_code == 200, replay.text
    topped = client.get("/credits/balance", params={"user_id": user_id}).json()
    assert topped["balance"] == free_balance + 10_000  # exactly once

    invoice = client.get("/credits/invoices", params={"user_id": user_id})
    assert invoice.status_code == 200, invoice.text
    body = invoice.json()
    assert body["unit"] == "credits" and body["period"]  # credits, never invented money

    # 6. UI wiring: every engine route the journey used is the one the
    #    browser pages call, and the utility pages stay out of the sitemap.
    api_text = (ROOT / "engine" / "api.py").read_text("utf-8")
    for route in ("/ats/upload", "/ats/score", "/improve/cv", "/cover/letter"):
        assert route in api_text, route
    ui_expectations = {
        WEB / "app" / "ats" / "AtsScanner.tsx": ("/ats/upload", "/ats/score"),
        WEB / "app" / "improve" / "CvImprover.tsx": ("/improve/cv",),
        WEB / "app" / "cover-letter" / "CoverLetterGenerator.tsx": ("/cover/letter",),
        WEB / "app" / "dashboard" / "Dashboard.tsx": ("/status", "/credits/balance"),
        WEB / "app" / "credits" / "dashboard" / "page.tsx": (
            "/credits/balance",
            "/credits/packs",
            "/credits/checkout",
        ),
    }
    for path, needles in ui_expectations.items():
        text = path.read_text("utf-8")
        assert '"use client"' in text, path
        for needle in needles:
            assert needle in text, f"{path} never calls {needle}"
    sitemap = (WEB / "app" / "sitemap.xml" / "route.ts").read_text("utf-8")
    # utility routes never masquerade as SEO pages (no <loc> entry)
    assert "${baseUrl}/dashboard" not in sitemap
    assert "${baseUrl}/credits/dashboard" not in sitemap
