"""FastAPI wrapper around the engine (§0.8, §22, task 9.4).

The free-tier Render deployment exposes ``GET /health`` plus the two
product endpoints: ``GET /status`` (build/usage summary for the dashboard
preview) and ``POST /ats/score`` (schema-valid ATS scoring, 9.4). On
startup a daemon thread (Approach 3, §22) begins the self-ping so the
container never hits the 15-minute cold sleep; a GitHub Actions cron
(§0.9) provides a second, independent keep-alive layer.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import __version__
from .ats import parse_resume, score_resume
from .errors import SchemaValidationError, VantiaError
from .json_utils import load_json, validate
from .keep_alive import start_self_ping
from .state_manager import VantiaState

_STARTED_AT = time.monotonic()

app = FastAPI(title="Vantia Engine", version=__version__, docs_url=None, redoc_url=None)


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


@app.on_event("startup")
def _startup() -> None:
    if os.environ.get("VANTIA_SELF_PING", "1") != "0":
        start_self_ping()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
