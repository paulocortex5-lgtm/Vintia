"""FastAPI wrapper around the engine (§0.8, §22, task 9.4).

The free-tier Render deployment exposes ``GET /health`` plus the product
endpoints: ``GET /status`` (build/usage summary for the dashboard
preview), ``POST /ats/score`` (schema-valid ATS scoring, 9.4), the credit
routes ``GET /credits/balance`` + ``GET /credits/estimate`` +
``GET /credits/packs`` + ``POST /credits/checkout`` (11.5 / 12.2 / 12.5)
and ``POST /paddle/webhook`` (12.3). On startup a daemon thread (Approach
3, §22) begins the self-ping so the container never hits the 15-minute
cold sleep; a GitHub Actions cron (§0.9) provides a second, independent
keep-alive layer.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import __version__
from .ats import parse_resume, score_resume
from .credits import (
    CREDIT_PACKS,
    create_checkout_transaction,
    default_ledger,
    default_meter,
    ensure_allowance,
    handle_webhook,
    load_credits_config,
    tier_of,
    tier_tokens,
)
from .errors import PaddleError, SchemaValidationError, VantiaError
from .json_utils import load_json, validate
from .keep_alive import start_self_ping
from .state_manager import VantiaState

_STARTED_AT = time.monotonic()

app = FastAPI(title="Vantia Engine", version=__version__, docs_url=None, redoc_url=None)


def _allowed_origins() -> list[str]:
    """Browser origins allowed to call the engine (Vercel → Render).

    Set ``VANTIA_ALLOWED_ORIGINS`` (comma-separated) in deployment; the
    default matches the Next dev server. Never ``*`` — the credit routes
    are keyed by ``user_id``. Read once at import: deployment config, not
    a per-request knob.
    """
    raw = os.environ.get("VANTIA_ALLOWED_ORIGINS", "http://localhost:3000")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["http://localhost:3000"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


class AtsScoreRequest(BaseModel):
    """Body of ``POST /ats/score`` (task 9.4)."""

    resume: dict[str, Any] | str = Field(
        ..., description="JSON profile document, or a server-side path to an uploaded resume"
    )
    job_title: str = ""
    job_description: str = ""
    job_location: str = ""
    resume_id: str = ""
    job_id: str = ""


@app.get("/health")
def health() -> dict:
    """Liveness probe used by Render, GitHub Actions, and the self-ping."""
    return {
        "status": "ok",
        "service": "vantia-engine",
        "version": __version__,
        "uptime_sec": round(time.monotonic() - _STARTED_AT, 1),
        "ts": datetime.now(UTC).isoformat(),
    }


@app.get("/status")
def status() -> dict[str, Any]:
    """Build-progress summary for the dashboard preview (task 9.4).

    Read-only: one state read, no lock — safe under concurrent requests.
    """
    state = VantiaState()
    if not state.exists:
        return {
            "initialised": False,
            "total": 0,
            "complete": 0,
            "pending": 0,
            "blocked": 0,
            "next_task": None,
            "run_count": 0,
            "last_completed_task": None,
            "readiness_pct": 0.0,
            "ts": datetime.now(UTC).isoformat(),
        }
    data = state.load()
    tasks: dict[str, Any] = data.get("tasks", {})
    complete = sum(1 for t in tasks.values() if t.get("status") == "complete")
    pending = sum(1 for t in tasks.values() if t.get("status") == "pending")
    ready = state.pending_tasks()
    return {
        "initialised": True,
        "total": len(tasks),
        "complete": complete,
        "pending": pending,
        "blocked": len(data.get("blocked", [])),
        "next_task": ready[0] if ready else None,
        "run_count": int(data.get("run_count", 0)),
        "last_completed_task": data.get("last_completed_task"),
        "readiness_pct": round(complete / len(tasks) * 100, 1) if tasks else 0.0,
        "ts": datetime.now(UTC).isoformat(),
    }


def _ats_schema() -> dict[str, Any]:
    path = os.path.join(os.path.dirname(__file__), "schemas", "ats_score.schema.json")
    schema = load_json(path)
    if schema is None:  # pragma: no cover — packaged file must exist
        raise VantiaError("ats_score.schema.json missing", code="schema_missing")
    return schema


@app.post("/ats/score")
def ats_score(request: AtsScoreRequest) -> dict[str, Any]:
    """Score a resume against a job (task 9.4) — schema-valid on every path.

    Bad uploads (missing file, empty/unparseable body) are **422** with the
    stable error code; a failure of our *own* payload against the schema is
    a bug and surfaces as **500**, never as a silently degraded report.
    """
    try:
        parsed = parse_resume(request.resume)
    except VantiaError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    report = score_resume(
        parsed,
        job_title=request.job_title,
        job_description=request.job_description,
        job_location=request.job_location,
    )
    payload = report.payload(resume_id=request.resume_id, job_id=request.job_id)
    try:
        validate(payload, _ats_schema())
    except SchemaValidationError as exc:
        raise HTTPException(status_code=500, detail=exc.as_dict()) from exc
    return {"report": payload, "schema": "ats_score.schema.json"}


def _require_user_id(user_id: str) -> str:
    """Shared 422 for the credit routes (stable code, same shape as 9.4)."""
    if not user_id:
        raise HTTPException(
            status_code=422,
            detail=VantiaError(
                "user_id query parameter is required", code="user_id_required"
            ).as_dict(),
        )
    return user_id


@app.get("/credits/balance")
def credits_balance(user_id: str = "") -> dict[str, Any]:
    """Balance + tier + pricing + recent entries for the credits dashboard (11.5).

    One payload the UI needs, so the frontend never has to stitch calls
    together. The read performs the idempotent this-month allowance grant
    (11.3) — a fresh user therefore sees their real free-tier balance, not
    a placeholder. No auth yet: Phase 8's workspace layer will bind
    ``user_id`` to the verified session; until then the id is caller-stated.
    """
    user_id = _require_user_id(user_id)
    config = load_credits_config()
    ledger = default_ledger()
    allowance = ensure_allowance(ledger, user_id, config=config)
    tier = tier_of(ledger, user_id)
    entries = ledger.entries(user_id)
    return {
        "user_id": user_id,
        "balance": ledger.balance(user_id),
        "tier": tier,
        "monthly_allowance": tier_tokens(tier, config),
        "allowance": {
            "granted": allowance["granted"],
            "month": allowance["month"],
            "amount": allowance["amount"],
        },
        "operations": dict(config.get("token_costs") or {}),
        "packs": list(config.get("credit_packs") or []),
        "entry_count": len(entries),
        "recent_entries": entries[-20:],
        "ts": datetime.now(UTC).isoformat(),
    }


@app.get("/credits/estimate")
def credits_estimate(user_id: str = "", operation: str = "") -> dict[str, Any]:
    """Cost/affordability of one operation before committing to it (11.5).

    Read-only: an unclaimed monthly allowance is *projected*, never
    granted here, so the estimate has no side effects (11.3). An
    unpriced operation is 422 with ``unknown_operation`` — it is never
    silently priced at zero.
    """
    user_id = _require_user_id(user_id)
    if not operation:
        raise HTTPException(
            status_code=422,
            detail=VantiaError(
                "operation query parameter is required", code="operation_required"
            ).as_dict(),
        )
    meter = default_meter()
    try:
        report = meter.estimate(user_id, operation)
    except VantiaError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    return {**report, "ts": datetime.now(UTC).isoformat()}


@app.get("/credits/packs")
def credits_packs() -> dict[str, Any]:
    """Credit packs + prices for the purchase page (task 12.5, UI data).

    Public (no ``user_id``): pack ids, token amounts and USD prices come
    from state ``credits.credit_packs``; when state carries no prices the
    response says ``price_usd: null`` instead of guessing one.
    """
    config = load_credits_config()
    packs = list(config.get("credit_packs") or [])
    if not packs:  # state degraded → derive from the code table, honestly unpriced
        packs = [
            {"id": pid, "tokens": tokens, "price_usd": None} for pid, tokens in CREDIT_PACKS.items()
        ]
    return {
        "packs": packs,
        "paddle_environment": os.environ.get("PADDLE_ENVIRONMENT", "sandbox"),
        "ts": datetime.now(UTC).isoformat(),
    }


class CheckoutRequest(BaseModel):
    """Body of ``POST /credits/checkout`` (task 12.2).

    Fields default to ``""`` so a missing key reaches the route and comes
    back as the same stable ``as_dict()`` 422 codes the other credit
    endpoints use, instead of a bare Pydantic validation list.
    """

    user_id: str = Field("", description="Purchasing user; flows into custom_data")
    pack_id: str = Field("", description="One of CREDIT_PACKS (pack_10k|pack_50k|pack_250k)")


@app.post("/credits/checkout")
def credits_checkout(request: CheckoutRequest) -> dict[str, Any]:
    """Open a Paddle Checkout for one credit pack (task 12.2).

    Stable 422s for caller mistakes (``user_id_required``,
    ``unknown_pack``); a Paddle/SDK/config failure surfaces as **502**
    ``paddle_error`` — never a fake URL and never a silent fallback.
    Paddle is the Merchant of Record (R57): this route never touches card
    data, it only returns ``transaction.checkout.url``.
    """
    if not request.user_id:
        raise HTTPException(
            status_code=422,
            detail=VantiaError("user_id is required", code="user_id_required").as_dict(),
        )
    if request.pack_id not in CREDIT_PACKS:
        raise HTTPException(
            status_code=422,
            detail=VantiaError(
                f"unknown credit pack {request.pack_id!r}; known: {', '.join(sorted(CREDIT_PACKS))}",
                code="unknown_pack",
            ).as_dict(),
        )
    try:
        checkout_url = create_checkout_transaction(request.user_id, request.pack_id)
    except PaddleError as exc:
        raise HTTPException(status_code=502, detail=exc.as_dict()) from exc
    return {
        "checkout_url": checkout_url,
        "pack_id": request.pack_id,
        "credits": CREDIT_PACKS[request.pack_id],
        "ts": datetime.now(UTC).isoformat(),
    }


@app.post("/paddle/webhook")
async def paddle_webhook(request: Request) -> dict[str, Any]:
    """Paddle notification endpoint (task 12.3 route, §G.7 / R51).

    Verifies ``Paddle-Signature`` (HMAC-SHA256, 5 s window), applies the
    idempotent ledger top-up and answers within Paddle's 5-second window.
    An invalid/malformed signature is **400** so Paddle stops retrying;
    processing failures surface honestly in the response body.
    """
    raw = await request.body()
    signature = request.headers.get("Paddle-Signature", "")
    try:
        result = handle_webhook(raw, signature)
    except PaddleError as exc:
        raise HTTPException(status_code=400, detail=exc.as_dict()) from exc
    return result


@app.on_event("startup")
def _startup() -> None:
    if os.environ.get("VANTIA_SELF_PING", "1") != "0":
        start_self_ping()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
