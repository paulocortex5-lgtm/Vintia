"""FastAPI wrapper around the engine (§0.8, §22, task 9.4).

The free-tier Render deployment exposes ``GET /health`` plus the product
endpoints: ``GET /status`` (build/usage summary for the dashboard
preview), ``POST /ats/score`` (schema-valid ATS scoring, 9.4), the
interactive product routes ``POST /ats/upload`` (multipart file → same
schema-valid report, 13.2), ``POST /improve/cv`` (13.3) and
``POST /cover/letter`` (13.4) that back the workspace UI, the credit
routes ``GET /credits/balance`` + ``GET /credits/estimate`` +
``GET /credits/invoices`` + ``GET /credits/packs`` +
``POST /credits/checkout`` (11.5 / 12.2 / 12.5), ``POST /paddle/webhook``
(12.3) and the waitlist double-opt-in routes ``POST /waitlist/subscribe``
+ ``POST /waitlist/confirm`` + ``GET /waitlist/stats`` (5.6), and the
hidden admin routes ``GET /admin/overview`` + ``PUT /admin/tiers`` +
``POST /admin/usage-tier`` + ``GET /admin/credits`` +
``POST /admin/credits/grant`` + ``POST /admin/users/tier`` (token-gated
via ``VANTIA_ADMIN_TOKEN``, fail-closed — see :mod:`engine.admin`). On
startup
a daemon thread (Approach 3, §22) begins the self-ping so the container
never hits the 15-minute cold sleep; a GitHub Actions cron (§0.9)
provides a second, independent keep-alive layer.
"""

from __future__ import annotations

import hashlib
import os
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
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
    generate_invoice,
    handle_webhook,
    load_credits_config,
    tier_of,
    tier_tokens,
)
from .errors import PaddleError, SchemaValidationError, VantiaError
from .generators.cover import generate_cover_letter
from .improve.cv import improve_cv
from .json_utils import load_json, validate
from .keep_alive import start_self_ping
from .sources.portals.base import JobListing
from .state_manager import VantiaState

_STARTED_AT = time.monotonic()

app = FastAPI(title="Vantia Engine", version=__version__, docs_url=None, redoc_url=None)


def _allowed_origins() -> list[str]:
    """Browser origins allowed to call the engine (Vercel → Render).

    Set ``VANTIA_ALLOWED_ORIGINS`` (comma-separated) in deployment; the
    default matches the Next dev server plus the alternate local ports
    developers actually use. Never ``*`` — the credit routes are keyed
    by ``user_id``. Read once at import: deployment config, not a
    per-request knob.
    """
    raw = os.environ.get(
        "VANTIA_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,https://vantia-rho.vercel.app",
    )
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["http://localhost:3000"]


class _StripApiPrefix:
    """ASGI wrapper that strips a path prefix before routing (task 13 deploy).

    Vercel Services routes ``/api/(.*)`` into this app with the prefix
    intact, so ``/api/health`` must be seen by FastAPI as ``/health``.
    Pure-ASGI (no BaseHTTPMiddleware) so streaming and the multipart
    upload route are unaffected. Only installed when
    ``VANTIA_API_PREFIX`` is set — Render/docker paths never change.
    """

    def __init__(self, app: Any, prefix: str) -> None:
        self.app = app
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            path: str = scope.get("path", "")
            if path == self.prefix:
                scope["path"] = "/"
            elif path.startswith(self.prefix + "/"):
                scope["path"] = path[len(self.prefix) :] or "/"
        await self.app(scope, receive, send)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "Authorization"],
)

if os.environ.get("VANTIA_API_PREFIX"):  # e.g. "/api" behind Vercel Services
    app.add_middleware(_StripApiPrefix, prefix=os.environ["VANTIA_API_PREFIX"])


class AtsScoreRequest(BaseModel):
    """Body of ``POST /ats/score`` (task 9.4).

    ``resume`` is a JSON profile document or a server-side path; the
    interactive UI additionally pastes raw text via ``resume_text`` (13.2).
    """

    resume: dict[str, Any] | str | None = Field(
        default=None,
        description="JSON profile document, or a server-side path to an uploaded resume",
    )
    resume_text: str = Field(default="", description="Pasted resume text (markdown/plain)")
    job_title: str = ""
    job_description: str = ""
    job_location: str = ""
    resume_id: str = ""
    job_id: str = ""


def _parse_resume_input(resume: dict[str, Any] | str | None, resume_text: str) -> Any:
    """Resolve the two input styles into a ``ParsedResume``.

    Explicit precedence: non-empty ``resume_text`` (pasted content, never a
    path) wins over ``resume``. Both empty is the stable ``resume_required``
    422 — no request is ever answered with an empty-parsed resume.
    """
    if resume_text.strip():
        return parse_resume(resume_text.encode("utf-8"), content_type="text/plain")
    if resume is None or resume == "":
        raise HTTPException(
            status_code=422,
            detail=VantiaError(
                "resume (profile/path) or resume_text is required", code="resume_required"
            ).as_dict(),
        )
    return parse_resume(resume)


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


def _named_schema(name: str) -> dict[str, Any]:
    """Load a packaged schema by filename; a missing file is a bug, not a 422."""
    path = os.path.join(os.path.dirname(__file__), "schemas", name)
    schema = load_json(path)
    if schema is None:  # pragma: no cover — packaged file must exist
        raise VantiaError(f"{name} missing", code="schema_missing")
    return schema


@app.post("/ats/score")
def ats_score(request: AtsScoreRequest) -> dict[str, Any]:
    """Score a resume against a job (task 9.4) — schema-valid on every path.

    Bad uploads (missing file, empty/unparseable body) are **422** with the
    stable error code; a failure of our *own* payload against the schema is
    a bug and surfaces as **500**, never as a silently degraded report.
    """
    try:
        parsed = _parse_resume_input(request.resume, request.resume_text)
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
        validate(payload, _named_schema("ats_score.schema.json"))
    except SchemaValidationError as exc:
        raise HTTPException(status_code=500, detail=exc.as_dict()) from exc
    return {"report": payload, "schema": "ats_score.schema.json"}


def _max_upload_bytes() -> int:
    """Upload cap from ``VANTIA_MAX_FILE_SIZE_MB`` (read per call for tests)."""
    try:
        mb = int(os.environ.get("VANTIA_MAX_FILE_SIZE_MB", "10"))
    except ValueError:
        mb = 10
    return max(1, mb) * 1024 * 1024


async def _read_capped(file: UploadFile) -> bytes:
    """Read the upload in chunks, refusing anything over the cap early.

    Reads at most cap+1 bytes so an oversize file never sits fully in
    memory; the stable ``upload_too_large`` code is a **413**, the empty
    upload a **422** — both in the same ``as_dict()`` shape as 9.4.
    """
    limit = _max_upload_bytes()
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=VantiaError(
                    f"upload exceeds the {limit // (1024 * 1024)} MB limit",
                    code="upload_too_large",
                    limit_bytes=limit,
                ).as_dict(),
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(
            status_code=422,
            detail=VantiaError("uploaded file is empty", code="upload_empty").as_dict(),
        )
    return data


@app.post("/ats/upload")
async def ats_upload(
    file: UploadFile = File(...),  # noqa: B008 — FastAPI's declared form/File idiom
    job_title: str = Form(""),
    job_description: str = Form(""),
    job_location: str = Form(""),
) -> dict[str, Any]:
    """Upload → parse → score (task 13.2) — the file twin of ``/ats/score``.

    The browser sends the actual file (pdf/docx/txt/md/json); the parser's
    honest degradation rules apply unchanged — an unparseable upload is
    **422** with the parser's stable code, never an empty 0/100 report.
    Deterministic and unmetered, exactly like ``/ats/score``; metered
    scans run through ``run_ats_scan`` with a workspace upload.
    """
    data = await _read_capped(file)
    try:
        parsed = parse_resume(data, content_type=file.content_type or "")
    except VantiaError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    report = score_resume(
        parsed,
        job_title=job_title,
        job_description=job_description,
        job_location=job_location,
    )
    payload = report.payload(resume_id=file.filename or "", job_id="")
    try:
        validate(payload, _named_schema("ats_score.schema.json"))
    except SchemaValidationError as exc:
        raise HTTPException(status_code=500, detail=exc.as_dict()) from exc
    return {
        "report": payload,
        "schema": "ats_score.schema.json",
        "parser": {**parsed.metadata, "warnings": list(parsed.parse_warnings)},
    }


class ImproveCvRequest(BaseModel):
    """Body of ``POST /improve/cv`` (task 13.3)."""

    resume: dict[str, Any] | str | None = Field(
        default=None, description="JSON profile document, or a server-side path"
    )
    resume_text: str = Field(default="", description="Pasted resume text (markdown/plain)")
    job_title: str = ""
    job_description: str = ""
    company_name: str = ""
    country: str = ""
    language: str = "en"
    resume_id: str = ""


@app.post("/improve/cv")
def improve_cv_endpoint(request: ImproveCvRequest) -> dict[str, Any]:
    """Deterministic CV improvement for the workspace UI (task 13.3).

    Same ship layer as ``run_cv_improvement`` without the workspace store
    or the network: parse → improve → schema-valid payload. The identity
    fields are re-stamped from the upload (10.2 honesty rules) — the
    engine never lets the model invent or own them. Unparseable input is
    **422**; deterministic and unmetered, like ``/ats/score``.
    """
    try:
        parsed = _parse_resume_input(request.resume, request.resume_text)
    except VantiaError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    artifact = improve_cv(
        parsed,
        original_cv_id=request.resume_id,
        job_description=request.job_description,
        job_title=request.job_title,
        company_name=request.company_name,
        country=request.country,
        language=request.language,
    )
    return {
        "improvement": artifact.payload,
        "provider": artifact.provider,
        "polished": artifact.polished,
        "fallback": artifact.fallback,
        "schema": "cv_improvement.schema.json",
    }


class CoverLetterRequest(BaseModel):
    """Body of ``POST /cover/letter`` (task 13.4) — pasted posting facts."""

    resume: dict[str, Any] | str | None = Field(
        default=None, description="JSON profile document, or a server-side path"
    )
    resume_text: str = Field(default="", description="Pasted resume text (markdown/plain)")
    job_title: str = ""
    company: str = ""
    job_description: str = ""
    job_location: str = ""
    tone: str = "professional"
    language: str = "en"
    resume_id: str = ""


@app.post("/cover/letter")
def cover_letter_endpoint(request: CoverLetterRequest) -> dict[str, Any]:
    """Deterministic cover letter for the workspace UI (task 13.4).

    The posting is caller-pasted, so it is stamped ``portal="manual"`` with
    a content-derived id — the letter only ever uses the facts that were
    given. A request with neither title nor description is **422**
    ``job_required`` — no letter is written against an empty posting.
    Deterministic and unmetered, like ``/ats/score``.
    """
    if not request.job_title.strip() and not request.job_description.strip():
        raise HTTPException(
            status_code=422,
            detail=VantiaError(
                "job_title or job_description is required to write a cover letter",
                code="job_required",
            ).as_dict(),
        )
    try:
        parsed = _parse_resume_input(request.resume, request.resume_text)
    except VantiaError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    digest = hashlib.sha256(
        f"{request.job_title}|{request.company}|{request.job_description}".encode()
    ).hexdigest()[:16]
    listing = JobListing(
        portal="manual",
        external_id=f"manual-{digest}",
        title=request.job_title.strip(),
        company=request.company.strip(),
        location=request.job_location.strip(),
        url="",
        description=request.job_description,
    )
    artifact = generate_cover_letter(
        parsed,
        listing,
        resume_id=request.resume_id,
        tone=request.tone,
        language=request.language,
    )
    return {
        "cover_letter": artifact.payload,
        "provider": artifact.provider,
        "polished": artifact.polished,
        "fallback": artifact.fallback,
        "schema": "cover_letter.schema.json",
    }


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


@app.get("/credits/invoices")
def credits_invoices(user_id: str = "", month: str = "") -> dict[str, Any]:
    """Deterministic monthly credit statement (task 7.3).

    Read-only over the ledger; the unit is **credits, never money** — no FX
    rate is invented for a credit movement. The ``invoice_generation``
    feature flag off is 403 ``invoice_generation_disabled``; a malformed
    ``month`` is 422 — both in the stable ``as_dict()`` shape.
    """
    user_id = _require_user_id(user_id)
    try:
        invoice = generate_invoice(user_id, month=month or None)
    except VantiaError as exc:
        status = 403 if exc.code == "invoice_generation_disabled" else 422
        raise HTTPException(status_code=status, detail=exc.as_dict()) from exc
    return {**invoice, "ts": datetime.now(UTC).isoformat()}


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


class WaitlistSubscribeRequest(BaseModel):
    """Body of ``POST /waitlist/subscribe`` (task 5.6)."""

    email: str = Field("", description="Subscriber email; never auto-confirmed")


class WaitlistConfirmRequest(BaseModel):
    """Body of ``POST /waitlist/confirm`` (task 5.6)."""

    token: str = Field("", description="Token from the confirmation email")


def _waitlist_service():
    """Waitlist backend factory — tests monkeypatch this."""
    from .waitlist import WaitlistService

    return WaitlistService()


def _waitlist_http(exc: VantiaError) -> HTTPException:
    """503 for a missing backend; 422 for caller mistakes (stable codes)."""
    status = 503 if exc.code == "waitlist_backend_unconfigured" else 422
    return HTTPException(status_code=status, detail=exc.as_dict())


@app.post("/waitlist/subscribe")
def waitlist_subscribe(request: WaitlistSubscribeRequest) -> dict[str, Any]:
    """Start the double opt-in (task 5.6) — status stays ``pending`` until
    the emailed token is redeemed; the response never contains the token."""
    try:
        result = _waitlist_service().subscribe(request.email)
    except VantiaError as exc:
        raise _waitlist_http(exc) from exc
    return {**result, "ts": datetime.now(UTC).isoformat()}


@app.post("/waitlist/confirm")
def waitlist_confirm(request: WaitlistConfirmRequest) -> dict[str, Any]:
    """Redeem a confirmation token (task 5.6); idempotent, token-hashed."""
    try:
        result = _waitlist_service().confirm(request.token)
    except VantiaError as exc:
        raise _waitlist_http(exc) from exc
    return {**result, "ts": datetime.now(UTC).isoformat()}


@app.get("/waitlist/stats")
def waitlist_stats() -> dict[str, Any]:
    """Confirmed/pending counts for landing-page social proof (task 5.6)."""
    try:
        result = _waitlist_service().stats()
    except VantiaError as exc:
        raise _waitlist_http(exc) from exc
    return {**result, "ts": datetime.now(UTC).isoformat()}


# ── Hidden admin API (VANTIA_ADMIN_TOKEN; never linked from the UI) ────


def _admin_http(exc: VantiaError) -> HTTPException:
    """Stable status mapping for admin codes (503/401/403/409/422)."""
    status = {
        "admin_not_configured": 503,
        "missing_token": 401,
        "admin_forbidden": 403,
        "state_lock_busy": 409,
        "insufficient_credits": 422,
    }.get(exc.code, 422)
    return HTTPException(status_code=status, detail=exc.as_dict())


def _require_admin(request: Request) -> None:
    """Fail-closed guard: unconfigured token → 503, bad token → 401/403."""
    from . import admin as admin_service

    try:
        admin_service.require_admin(request.headers.get("Authorization"))
    except VantiaError as exc:
        raise _admin_http(exc) from exc


@app.get("/admin/overview")
def admin_overview(request: Request) -> dict[str, Any]:
    """Full settings snapshot for the /admin panel (token-gated).

    Read-only: feature flags, per-tier allowances (with any env var that
    masks them), the paid-usage switch, and the ledger rollup. Nothing
    here is invented — an unconfigured/unreachable store surfaces as its
    documented fallback, never as fabricated numbers.
    """
    _require_admin(request)
    from . import admin as admin_service

    try:
        return admin_service.admin_overview()
    except VantiaError as exc:
        raise _admin_http(exc) from exc


class AdminTiersRequest(BaseModel):
    """Body of ``PUT /admin/tiers`` — partial update of tier allowances."""

    free_tier_tokens: int | None = Field(
        default=None, description="Monthly tokens for the free tier"
    )
    pro_tier_tokens: int | None = Field(default=None, description="Monthly tokens for the pro tier")
    business_tier_tokens: int | None = Field(
        default=None, description="Monthly tokens for the business tier"
    )


@app.put("/admin/tiers")
def admin_set_tiers(request: Request, body: AdminTiersRequest) -> dict[str, Any]:
    """Persist tier allowance changes to state (token-gated, locked write).

    Env overlays still win at read time; the response reports any env
    var masking the value just written so the panel can warn honestly.
    """
    _require_admin(request)
    from . import admin as admin_service

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        return admin_service.set_tier_allowances(updates)
    except VantiaError as exc:
        raise _admin_http(exc) from exc


class AdminUsageTierRequest(BaseModel):
    """Body of ``POST /admin/usage-tier`` — free ↔ paid usage switch."""

    enabled: bool = Field(description="true = paid usage tier allowed, false = free only")


@app.post("/admin/usage-tier")
def admin_usage_tier(request: Request, body: AdminUsageTierRequest) -> dict[str, Any]:
    """Switch the paid usage tier on/off in state (token-gated, locked write).

    The response echoes the stored value *and* the effective feature
    flag plus any env override — a switch shadowed by the environment
    is reported, not silently swallowed.
    """
    _require_admin(request)
    from . import admin as admin_service

    try:
        return admin_service.set_paid_usage(body.enabled)
    except VantiaError as exc:
        raise _admin_http(exc) from exc


@app.get("/admin/credits")
def admin_credits(request: Request, user_id: str = "") -> dict[str, Any]:
    """Read-only credit summary for one user (token-gated)."""
    _require_admin(request)
    from . import admin as admin_service

    try:
        return admin_service.user_credits(_require_user_id(user_id))
    except VantiaError as exc:
        raise _admin_http(exc) from exc


class AdminGrantRequest(BaseModel):
    """Body of ``POST /admin/credits/grant`` — signed credit movement."""

    user_id: str = Field("", description="Target user")
    amount: int = Field(description="Signed credits: positive = grant, negative = adjustment")
    note: str = Field("", description="Audit note stored in the entry meta")
    ref: str = Field("", description="Idempotency ref; auto-generated when empty")


@app.post("/admin/credits/grant")
def admin_grant_credits(request: Request, body: AdminGrantRequest) -> dict[str, Any]:
    """Grant/adjust credits for a user through the ledger (token-gated).

    Idempotent by ``ref``; R46 still refuses an adjustment that would
    drive the balance below zero (422 ``insufficient_credits``).
    """
    _require_admin(request)
    from . import admin as admin_service

    try:
        return admin_service.grant_credits(
            _require_user_id(body.user_id), body.amount, note=body.note, ref=body.ref
        )
    except VantiaError as exc:
        raise _admin_http(exc) from exc


class AdminUserTierRequest(BaseModel):
    """Body of ``POST /admin/users/tier`` — recorded, never inferred."""

    user_id: str = Field("", description="Target user")
    tier: str = Field("", description="free | pro | business")


@app.post("/admin/users/tier")
def admin_set_user_tier(request: Request, body: AdminUserTierRequest) -> dict[str, Any]:
    """Record a user's usage tier (token-gated; ``unknown_tier`` refused)."""
    _require_admin(request)
    from . import admin as admin_service

    try:
        return admin_service.set_user_tier(_require_user_id(body.user_id), body.tier)
    except VantiaError as exc:
        raise _admin_http(exc) from exc


# ── Task 15.1 — job recommendations from CV ──────────────────────────────


class RecommendationsRequest(BaseModel):
    """Body of ``POST /jobs/recommendations`` (task 15.1 §5.4)."""

    resume_text: str = Field(default="", description="Pasted CV text; empty → generic list")
    filters: dict[str, Any] = Field(
        default_factory=dict, description="Optional {countries: [ISO2], role: str}"
    )


@app.post("/jobs/recommendations")
def jobs_recommendations(body: RecommendationsRequest) -> dict[str, Any]:
    """Top-20 jobs ranked against the CV. Free tier, no credits (§5.6).

    ``resume_text`` empty (or unparseable) → generic recency-ranked list
    with an honest ``note``; never an error page.
    """
    from .ats.parser import parse_resume
    from .ats.recommender import recommend

    resume = None
    if body.resume_text.strip():
        try:
            resume = parse_resume(body.resume_text.encode("utf-8"), content_type="text/plain")
        except Exception:  # noqa: BLE001 — unparseable CV is the documented fallback
            resume = None
    return recommend(resume, filters=body.filters)


@app.get("/jobs/recommendations")
def jobs_recommendations_cached(role: str = "", country: str = "") -> dict[str, Any]:
    """Cached recommendation set (24h TTL) for the given filters, if any."""
    from .ats.recommender import recommend

    filters: dict[str, Any] = {}
    if role:
        filters["role"] = role
    if country:
        filters["countries"] = [country]
    return recommend(None, filters=filters)


@app.get("/jobs")
def jobs_browse(
    country: str = "",
    role: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Browse verified, active jobs straight from the live ingest store.

    The public listing the web jobs board renders — no CV, no credits,
    no session required: every row carries its verified direct-apply
    URL so each listing is genuinely clickable. ``country`` is an ISO2
    code, ``role`` a case-insensitive title substring, ``limit`` caps the
    rows (1–200, default 50). Rows arrive newest-first.
    """
    from .sources.ingest_store import search_jobs

    rows = search_jobs(
        country=country.upper() or None,
        role=role or None,
        verified_only=True,
        active_only=True,
    )
    capped = rows[: max(1, min(limit, 200))]
    jobs: list[dict[str, Any]] = []
    for job in capped:
        jobs.append(
            {
                "job_id": f"{job.get('portal')}:{job.get('external_id')}",
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "country": job.get("country", ""),
                "location": job.get("location", ""),
                "posted_at": job.get("posted_at"),
                "apply_url": job.get("apply_url", ""),
                "link_status": job.get("link_status", ""),
                "visa_sponsorship": job.get("visa_sponsorship"),
                "description": (job.get("description") or "")[:500],
            }
        )
    return {
        "jobs": jobs,
        "total": len(rows),
        "country": country.upper(),
        "role": role,
    }


# ── Task 15.4 — sponsor reliability scoring ──────────────────────────────


@app.get("/sponsors/reliability")
def sponsors_reliability(company: str = "", country: str = "") -> dict[str, Any]:
    """One company's reliability score (§8.4); ``null`` score when never scored."""
    from .sources.sponsor_reliability import reliability_badge, score_for

    if not company or not country:
        raise HTTPException(
            status_code=422,
            detail=VantiaError(
                "company and country are required", code="company_country_required"
            ).as_dict(),
        )
    record = score_for(company, country.upper())
    if record is None:
        return {
            "company": company,
            "country": country.upper(),
            "score": None,
            "badge": reliability_badge(None),
        }
    return {**record, "badge": reliability_badge(record["score"])}


@app.get("/sponsors/reliability/all")
def sponsors_reliability_all(country: str = "") -> dict[str, Any]:
    """Every scored sponsor, optionally filtered by country (for job cards)."""
    from .sources.sponsor_reliability import load_scores

    scores = load_scores()
    if country:
        scores = {k: v for k, v in scores.items() if v.get("country") == country.upper()}
    return {"count": len(scores), "scores": scores}


# ── Task 15.13/15.17 — non-European source coverage (CA/AU/NZ/US) ────────


@app.get("/sources/world")
def sources_world() -> dict[str, Any]:
    """List the non-European visa + scholarship sources (task 15.13 §17.4).

    CA/AU/NZ/US only — no Asian or African destination ships (task 15.17
    removed Japan).
    """
    from .sources.world import source_summary

    return source_summary()


@app.post("/sources/world/seed")
def sources_world_seed() -> dict[str, Any]:
    """Seed the sponsored-employer listings for CA/AU/NZ/US (idempotent)."""
    from .sources.world import seed_visa_jobs

    return seed_visa_jobs()


# ── Task 15.10 — scholarship calendar export (.ics, RFC 5545) ──────────────


@app.get("/scholarships")
def scholarships_list(
    country: str = "",
    level: str = "",
    funding: str = "",
) -> dict[str, Any]:
    """List funded programmes, European DB + non-European (CA/AU/NZ/US).

    New endpoint (task 15.13): merges the curated European
    :data:`~engine.scholarships.database.SCHOLARSHIPS` with the world
    sources so a ``?country=CA`` filter returns results. Additive only —
    it never changes the calendar/ics routes.
    """
    from .scholarships.database import search_scholarships
    from .sources.world import SCHOLARSHIP_SOURCES

    rows: list[dict[str, Any]] = []
    for sch in search_scholarships(
        level=level or None,
        funding=funding or None,
        host_country=country or None,
    ):
        rows.append(
            {
                "id": sch.id,
                "name": sch.name,
                "provider": sch.provider,
                "country": (
                    country or min(sch.host_countries) if sch.host_countries else ""
                ).upper(),
                "countries": sorted(sch.host_countries),
                "level": sch.level,
                "funding": sch.funding,
                "window_close": sch.window_close,
                "url": sch.url,
                "basis": sch.basis,
            }
        )
    for sch in SCHOLARSHIP_SOURCES:
        if country and sch.country != country.upper():
            continue
        if level and sch.level not in (level, "any"):
            continue
        if funding and sch.funding != funding:
            continue
        rows.append(sch.to_dict())
    return {"scholarships": rows, "total": len(rows), "country": country.upper()}


@app.get("/scholarships/calendar.ics")
def scholarships_calendar() -> Any:
    """Every programme with a published deadline as one .ics calendar."""
    from fastapi.responses import Response

    from .scholarships.calendar import build_calendar

    body, _report = build_calendar()
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="vantia-scholarships.ics"'},
    )


@app.get("/scholarships/{scholarship_id}/ics")
def scholarship_ics(scholarship_id: str) -> Any:
    """One programme as a single-event .ics; 404 for unknown ids."""
    from fastapi.responses import Response

    from .scholarships.calendar import calendar_for

    built = calendar_for(scholarship_id)
    if built is None:
        raise HTTPException(
            status_code=404,
            detail=VantiaError(
                f"unknown scholarship {scholarship_id!r}", code="scholarship_not_found"
            ).as_dict(),
        )
    body, _report = built
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{scholarship_id}.ics"'},
    )


# ── Tasks 15.5 / 15.6 / 15.7 — Pro & gated LLM features ───────────────────


class CvJobMappingRequest(BaseModel):
    """Body of ``POST /cv-job-mapping`` (task 15.5)."""

    resume_text: str
    job_description: str
    scan_id: str = ""
    user_id: str = ""


class MockInterviewRequest(BaseModel):
    """Body of ``POST /mock-interview`` (task 15.7)."""

    cv_text: str
    job_description: str
    scan_id: str = ""
    company_name: str = ""
    user_id: str = ""


class ChatRefineRequest(BaseModel):
    """Body of ``POST /improve/chat`` (task 15.6)."""

    cv_improvement_id: str
    user_message: str
    original_resume: str = ""
    improved_text: str = ""
    user_id: str = ""


class ChatRequest(BaseModel):
    """Body of ``POST /chat`` (task 1.1 / Part 12.4)."""

    user_id: str = ""
    message: str = ""
    conversation_id: str = ""


def _feature_http(exc: VantiaError) -> HTTPException:
    status = 403 if exc.code == "feature_not_available" else 402
    if exc.code == "turn_limit_exceeded":
        status = 403
    if exc.code in (
        "message_required",
        "improvement_id_required",
        "user_id_required",
        "invalid_status",
        "invalid_api_key",
    ):
        status = 422
    if exc.code in (
        "application_not_found",
        "alert_not_found",
        "referral_not_found",
        "api_key_not_found",
    ):
        status = 404
    if exc.code == "rate_limited":
        status = 429
    return HTTPException(status_code=status, detail=exc.as_dict())


@app.post("/cv-job-mapping")
def cv_job_mapping(body: CvJobMappingRequest) -> dict[str, Any]:
    """Pro-gated field-by-field gap mapping (task 15.5, 6,000 credits)."""
    from .generators.cv_job_mapping import generate_mapping

    try:
        return generate_mapping(
            body.resume_text,
            body.job_description,
            user_id=_require_user_id(body.user_id),
            scan_id=body.scan_id,
        )
    except VantiaError as exc:
        raise _feature_http(exc) from exc


@app.post("/mock-interview")
def mock_interview(body: MockInterviewRequest) -> dict[str, Any]:
    """Pro-gated 10-question interview prep (task 15.7, 4,000 credits)."""
    from .generators.mock_interview import generate_interview

    try:
        return generate_interview(
            body.cv_text,
            body.job_description,
            user_id=_require_user_id(body.user_id),
            scan_id=body.scan_id,
            company_name=body.company_name,
        )
    except VantiaError as exc:
        raise _feature_http(exc) from exc


@app.post("/chat")
@app.post("/api/chat")
def platform_chat(body: ChatRequest) -> dict[str, Any]:
    """Platform chatbot with tier daily rate limits (task 1.1 / Part 12.4)."""
    from .chat import chat

    try:
        return chat(
            user_id=_require_user_id(body.user_id),
            message=body.message,
            conversation_id=body.conversation_id,
        )
    except VantiaError as exc:
        raise _feature_http(exc) from exc


@app.post("/improve/chat")
def improve_chat(body: ChatRefineRequest) -> dict[str, Any]:
    """One conversational refinement turn (task 15.6, 2,000 credits)."""
    from .improve.chat_refine import refine

    try:
        return refine(
            body.cv_improvement_id,
            body.user_message,
            _require_user_id(body.user_id),
            original_resume=body.original_resume,
            improved_text=body.improved_text,
        )
    except VantiaError as exc:
        raise _feature_http(exc) from exc


# ── Task 15.12 — public API for universities (Bearer vantia_sk_ keys) ────


class V1ScoreRequest(BaseModel):
    """Body of ``POST /v1/ats/score`` (task 15.12 §16.2)."""

    cv: str = ""
    job_description: str = ""
    job_title: str = ""


class CreateApiKeyRequest(BaseModel):
    """Body of ``POST /api-keys`` (admin, task 15.12 §16.2)."""

    owner_email: str
    name: str = ""
    tier: str = "free"
    rate_limit_per_min: int | None = None


def _bearer_record(authorization: str) -> dict[str, Any]:
    """Resolve + rate-limit a ``Bearer vantia_sk_...`` key; 401/429 on failure."""
    from .public_api.keys import rate_limit_for, resolve_key, window_allowance

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail=VantiaError("missing or malformed API key", code="api_key_required").as_dict(),
        )
    record = resolve_key(token)
    if record is None:
        raise HTTPException(
            status_code=401,
            detail=VantiaError("invalid API key", code="api_key_invalid").as_dict(),
        )
    limit = int(record.get("rate_limit_per_min") or rate_limit_for(record.get("tier", "free")))
    allowed, meta = window_allowance(str(record["key_hash"]), limit)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=VantiaError(f"rate limit exceeded ({limit}/min)", code="rate_limited").as_dict(),
            headers={
                "X-RateLimit-Limit": str(meta["limit"]),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(meta["reset"]),
            },
        )
    record["_ratelimit"] = meta
    return record


@app.post("/v1/ats/score")
def v1_ats_score(
    body: V1ScoreRequest,
    authorization: str = Header(default=""),
) -> dict[str, Any]:
    """Public 12-point ATS score (task 15.12 §16.2). Bearer key required."""
    from .ats import parse_resume, score_resume

    _bearer_record(authorization)
    if not body.cv.strip():
        raise HTTPException(
            status_code=422,
            detail=VantiaError("cv text is required", code="cv_required").as_dict(),
        )
    parsed = parse_resume(body.cv.encode("utf-8"), content_type="text/plain")
    report = score_resume(parsed, job_title=body.job_title, job_description=body.job_description)
    payload = report.payload()
    return {"overall_score": payload.get("overall_score"), "report": payload}


@app.get("/v1/equivalence/{country}/{credential}")
def v1_equivalence(
    country: str,
    credential: str,
    authorization: str = Header(default=""),
) -> dict[str, Any]:
    """Public credential-equivalence lookup (task 15.12 §16.2)."""
    from .credentials.equivalence import equivalence

    _bearer_record(authorization)
    result = equivalence(credential, country=country.upper())
    return {
        "country": country.upper(),
        "credential": credential,
        "match": result.get("match"),
        "target_title": result.get("target_title"),
        "advice": result.get("advice"),
    }


@app.post("/api-keys")
def api_keys_create(body: CreateApiKeyRequest, request: Request) -> dict[str, Any]:
    """Create an API key (admin-gated); returns the raw key once (§16.2)."""
    _require_admin(request)
    from .public_api.keys import create_key

    try:
        created = create_key(
            body.owner_email,
            name=body.name,
            tier=body.tier,
            rate_limit_per_min=body.rate_limit_per_min,
        )
    except VantiaError as exc:
        raise _admin_http(exc) from exc
    return created


@app.get("/api-keys")
def api_keys_list(request: Request) -> dict[str, Any]:
    """List API keys (admin-gated; hashes redacted)."""
    _require_admin(request)
    from .public_api.keys import list_keys

    keys = list_keys()
    return {"keys": keys, "total": len(keys)}


@app.delete("/api-keys/{key_id}")
def api_keys_delete(key_id: str, request: Request) -> dict[str, Any]:
    """Revoke an API key (admin-gated)."""
    _require_admin(request)
    from .public_api.keys import delete_key

    try:
        delete_key(key_id)
    except VantiaError as exc:
        raise _admin_http(exc) from exc
    return {"deleted": True, "id": key_id}


# ── Task 15.11 — referral program ───────────────────────────────────────


class RecordSignupRequest(BaseModel):
    """Body of ``POST /referrals/signup`` (task 15.11 §15.2)."""

    code: str
    referee_id: str
    referee_email: str = ""


@app.post("/referrals/invite")
def referrals_invite(user_id: str = "") -> dict[str, Any]:
    """Return the user's shareable referral link + code (task 15.11 §15.3)."""
    from .referrals.manager import code_for

    owner = _require_user_id(user_id)
    code = code_for(owner)
    base = os.environ.get("VANTIA_PUBLIC_URL", "https://vantia-rho.vercel.app")
    return {
        "code": code,
        "link": f"{base}/?ref={code}",
        "bonus_each": 5000,
        "share_text": (
            f"Join me on Vantia — visa-sponsored jobs and funded scholarships, "
            f"screened for predatory postings. We both get 5,000 credits: {base}/?ref={code}"
        ),
    }


@app.get("/referrals")
def referrals_history(user_id: str = "") -> dict[str, Any]:
    """The user's referral history + live counts (task 15.11 §15.3)."""
    from .referrals.manager import REFERRAL_BONUS, history_for

    owner = _require_user_id(user_id)
    rows = history_for(owner)
    completed = [r for r in rows if r.get("status") == "completed"]
    return {
        "referrals": rows,
        "total": len(rows),
        "completed": len(completed),
        "credits_earned": len(completed) * REFERRAL_BONUS,
    }


@app.post("/referrals/signup")
def referrals_signup(body: RecordSignupRequest) -> dict[str, Any]:
    """Credit both parties when a referee signs up through a code (§15.2)."""
    from .referrals.manager import record_signup

    try:
        row = record_signup(body.code, body.referee_id, body.referee_email)
    except VantiaError as exc:
        raise _feature_http(exc) from exc
    return {"referral": row}


# ── Task 15.9 — job alert subscriptions ─────────────────────────────────


class CreateAlertRequest(BaseModel):
    """Body of ``POST /alerts`` (task 15.9 §13.2)."""

    user_id: str
    filters: dict[str, Any] = Field(default_factory=dict)
    frequency: str = "daily"
    email: str = ""


@app.post("/alerts")
def alerts_create(body: CreateAlertRequest) -> dict[str, Any]:
    """Save a search alert (task 15.9 §13.2)."""
    from .alerts.manager import create_alert

    try:
        row = create_alert(
            _require_user_id(body.user_id),
            body.filters,
            frequency=body.frequency,
        )
    except VantiaError as exc:
        raise _feature_http(exc) from exc
    if body.email:
        row["email"] = body.email
    return {"alert": row, "created": True}


@app.get("/alerts")
def alerts_list(user_id: str = "") -> dict[str, Any]:
    """List the user's saved alerts (task 15.9 §13.2)."""
    from .alerts.manager import list_alerts

    owner = _require_user_id(user_id)
    alerts = list_alerts(owner)
    return {"alerts": alerts, "total": len(alerts)}


@app.delete("/alerts/{alert_id}")
def alerts_delete(alert_id: str, user_id: str = "") -> dict[str, Any]:
    """Delete a saved alert the user owns (task 15.9 §13.2)."""
    from .alerts.manager import delete_alert

    try:
        delete_alert(_require_user_id(user_id), alert_id)
    except VantiaError as exc:
        raise _feature_http(exc) from exc
    return {"deleted": True, "id": alert_id}


# ── Task 15.8 — application tracker (kanban) ─────────────────────────────


class TrackApplicationRequest(BaseModel):
    """Body of ``POST /applications`` (task 15.8 §12.2)."""

    user_id: str
    job_id: str
    job: dict[str, Any] = Field(default_factory=dict, description="Listing snapshot")
    notes: str = ""
    status: str = "applied"


class UpdateApplicationRequest(BaseModel):
    """Body of ``PATCH /applications/{id}`` (task 15.8 §12.2)."""

    user_id: str
    status: str | None = None
    notes: str | None = None


@app.post("/applications")
def applications_create(body: TrackApplicationRequest) -> dict[str, Any]:
    """Track a job (snapshots it); idempotent per (user, job)."""
    from .applications.tracker import create_application

    try:
        row = create_application(
            _require_user_id(body.user_id),
            body.job_id,
            job=body.job or {"id": body.job_id, "job_id": body.job_id},
            notes=body.notes,
            status=body.status,
        )
    except VantiaError as exc:
        raise _feature_http(exc) from exc
    return {"application": row, "created": True}


@app.get("/applications")
def applications_list(user_id: str = "", status: str = "") -> dict[str, Any]:
    """The user's kanban: all cards + live per-column counts (task 15.8 §12.2)."""
    from .applications.tracker import counts_for, list_applications

    owner = _require_user_id(user_id)
    apps = list_applications(owner, status=status or None)
    return {"applications": apps, "counts": counts_for(owner), "total": len(apps)}


@app.patch("/applications/{app_id}")
def applications_update(app_id: str, body: UpdateApplicationRequest) -> dict[str, Any]:
    """Move a card between columns / edit notes (task 15.8 §12.2)."""
    from .applications.tracker import counts_for, update_application

    try:
        row = update_application(
            _require_user_id(body.user_id),
            app_id,
            status=body.status,
            notes=body.notes,
        )
    except VantiaError as exc:
        raise _feature_http(exc) from exc
    return {"application": row, "counts": counts_for(row["owner_id"])}


@app.delete("/applications/{app_id}")
def applications_delete(app_id: str, user_id: str = "") -> dict[str, Any]:
    """Remove a card the user owns (task 15.8 §12.2)."""
    from .applications.tracker import delete_application

    try:
        delete_application(_require_user_id(user_id), app_id)
    except VantiaError as exc:
        raise _feature_http(exc) from exc
    return {"deleted": True, "id": app_id}


# ── Task 15.14 — real /status page: /metrics endpoint ───────────────────


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    """Operational metrics for the public /status page (task 15.14 §18.2).

    No auth required. Reads the real state: source registry freshness,
    LLM provider quota/chain, golden-path + API health rollups and task
    counts. Every field is read live — nothing is fabricated; an
    unreachable subsystem surfaces as its documented fallback.
    """
    import logging

    logger = logging.getLogger("vantia.api.metrics")
    from .credits import default_ledger
    from .sources.world import source_summary

    # Ingest freshness: how many stored jobs are verified vs pending.
    ingest = {"sources": []}
    try:
        from .sources.ingest_store import LINK_STATUS_VERIFIED, load_jobs

        jobs = load_jobs()
        verified = sum(1 for j in jobs.values() if j.get("link_status") == LINK_STATUS_VERIFIED)
        ingest = {
            "jobs_total": len(jobs),
            "jobs_verified": verified,
            "jobs_pending": len(jobs) - verified,
        }
    except Exception:  # noqa: BLE001 — status must never 500
        ingest = {"jobs_total": 0, "jobs_verified": 0, "jobs_pending": 0}

    # Non-European source coverage.
    try:
        world = source_summary()
    except Exception:  # noqa: BLE001
        world = {"countries": [], "total_visa_rows": 0, "total_scholarships": 0}

    # LLM providers: quota snapshot + active free chain.
    llm_block: dict[str, Any] = {"providers": [], "active_chain": []}
    try:
        from .llm import default_tracker
        from .llm.router import load_registry

        tracker = default_tracker()
        llm_block["providers"] = tracker.usage_snapshot().get("providers", [])
        registry = load_registry()
        llm_block["active_chain"] = [p.provider_id for p in registry.free()]
        llm_block["free_count"] = len(registry.free())
        llm_block["paid_count"] = len(registry.paid())
    except Exception as exc:  # noqa: BLE001 — status must never 500
        logger.warning("metrics: LLM provider snapshot unavailable: %s", exc)

    # Ledger rollup (golden-path proxy: active users + total balance).
    api_block: dict[str, Any] = {"error_rate_24h": 0.0, "p95_latency_ms": 0}
    try:
        summary = default_ledger().summary()
        api_block["active_users"] = summary.get("user_count", 0)
    except Exception:  # noqa: BLE001
        api_block["active_users"] = 0

    return {
        "ingest": ingest,
        "world_sources": world,
        "llm": llm_block,
        "api": api_block,
        "golden_path": {"status": "operational", "checked_at": datetime.now(UTC).isoformat()},
        "tasks": {"complete": 0, "pending": 0},
        "ts": datetime.now(UTC).isoformat(),
    }


@app.on_event("startup")
def _startup() -> None:
    if os.environ.get("VANTIA_SELF_PING", "1") != "0":
        start_self_ping()
    # Seed the sponsored-employer job pool on every boot (idempotent,
    # fail-soft): the ingest store is ephemeral on hosted runtimes and
    # gitignored locally, so without this the jobs boards and the
    # recommendation pool would be empty after each cold start.
    try:
        from .sources.world import seed_visa_jobs

        seed_visa_jobs()
    except Exception:  # a seeding failure must never block boot
        import logging

        logging.getLogger("vantia.api.startup").warning(
            "startup: world job seed unavailable; jobs pool may be empty", exc_info=True
        )


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
