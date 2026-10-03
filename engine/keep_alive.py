"""Self-ping keep-alive (Approach 3, §22).

A daemon thread GETs the backend ``/health`` endpoint every
``VANTIA_SELF_PING_INTERVAL_SEC`` seconds so a free-tier Render container
never enters the 15-minute cold-sleep. GitHub Actions runs the same ping
on a 14-minute cron (§0.9); both layers are complementary.
"""

from __future__ import annotations

import logging
import os
import threading
import time

import httpx

LOGGER = logging.getLogger("vantia.keep_alive")

DEFAULT_INTERVAL_SEC = 600  # 10 minutes, comfortably inside Render's 15-min window

_thread: threading.Thread | None = None


def start_self_ping(
    interval_sec: int | None = None,
    target_url: str | None = None,
) -> threading.Thread | None:
    """Start the daemon ping loop. Idempotent; returns the thread or None."""
    global _thread
    if _thread is not None:
        return _thread
    interval = (
        interval_sec
        if interval_sec is not None
        else int(os.environ.get("VANTIA_SELF_PING_INTERVAL_SEC", DEFAULT_INTERVAL_SEC))
    )
    if interval <= 0:
        LOGGER.warning("self-ping disabled (interval=%d)", interval)
        return None
    base = (
        target_url
        or os.environ.get("VANTIA_BACKEND_URL", "http://127.0.0.1:8000")
    ).rstrip("/")
    path = os.environ.get("VANTIA_HEALTH_ENDPOINT", "/health")
    url = f"{base}{path}"

    def loop() -> None:
        LOGGER.info("self-ping started: %s every %ds", url, interval)
        while True:
            time.sleep(interval)
            try:
                resp = httpx.get(url, timeout=10.0)
                LOGGER.info("self-ping ok: %s", resp.status_code)
            except httpx.HTTPError as exc:
                LOGGER.warning("self-ping failed: %s", exc)

    _thread = threading.Thread(target=loop, name="vantia-self-ping", daemon=True)
    _thread.start()
    return _thread
