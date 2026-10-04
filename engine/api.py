"""FastAPI wrapper around the engine (§0.8, §22).

The free-tier Render deployment exposes ``GET /health``. On startup a
daemon thread (Approach 3, §22) begins the self-ping so the container
never hits the 15-minute cold sleep; a GitHub Actions cron (§0.9) provides
a second, independent keep-alive layer.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from fastapi import FastAPI

from . import __version__
from .keep_alive import start_self_ping

_STARTED_AT = time.monotonic()

app = FastAPI(title="Vantia Engine", version=__version__, docs_url=None, redoc_url=None)


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


@app.on_event("startup")
def _startup() -> None:
    if os.environ.get("VANTIA_SELF_PING", "1") != "0":
        start_self_ping()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
