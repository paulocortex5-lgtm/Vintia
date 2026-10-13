"""Job alert subscriptions (task 15.9).

A saved search that emails the user the top new matching jobs on a
schedule (daily or weekly). Alerts are stored locally-first in
``.vantia/alerts/job_alerts.json`` with a best-effort Supabase mirror.

Design (repo rules carried over):

* **Local-first / git-authoritative** — the JSON store is the source of
  truth; the Supabase mirror never raises.
* **Frequency vocabulary** fixed (§13.1): daily, weekly — anything else
  refused, never silently coerced.
* **Digest idempotency** — :func:`jobs_since` keys off ``last_sent_at`` so
  a re-run inside the same window sends nothing twice; a job already in a
  prior digest is excluded by its posting timestamp.
* **Owner isolation (R26)** — every row carries ``user_id``; reads and
  writes are scoped to it.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from ..errors import VantiaError
from ..json_utils import atomic_write_json, load_json
from ..logging_config import utc_now

__all__ = [
    "FREQUENCIES",
    "INTERVAL",
    "alerts_for",
    "create_alert",
    "delete_alert",
    "due_alerts",
    "jobs_since",
    "list_alerts",
    "mark_sent",
    "matches_filters",
]

LOGGER = logging.getLogger("vantia.alerts.manager")

STORE_VERSION = 1

#: §13.1 frequency vocabulary.
FREQUENCIES = ("daily", "weekly")

#: Digest window per frequency.
INTERVAL = {"daily": timedelta(days=1), "weekly": timedelta(days=7)}

_store_lock = threading.RLock()


def _default_dir() -> str:
    return os.environ.get("VANTIA_ALERTS_DIR", os.path.join(".vantia", "alerts"))


def _store_file() -> str:
    return os.path.join(_default_dir(), "job_alerts.json")


def _load_all() -> dict[str, Any]:
    data = load_json(_store_file())
    if not isinstance(data, dict) or not isinstance(data.get("alerts"), dict):
        return {"version": STORE_VERSION, "alerts": {}}
    return data


def _save_all(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_store_file()), exist_ok=True)
    atomic_write_json(_store_file(), data)


def _validate_frequency(freq: str) -> str:
    if freq not in FREQUENCIES:
        raise VantiaError(
            f"unknown frequency {freq!r}; known: {', '.join(FREQUENCIES)}",
            code="invalid_frequency",
        )
    return freq


def _new_id(user_id: str) -> str:
    return hashlib.sha256(f"{user_id}:{utc_now()}".encode()).hexdigest()[:16]


def matches_filters(job: dict[str, Any], filters: dict[str, Any]) -> bool:
    """True when a job satisfies an alert's saved filters.

    Filters may carry ``countries`` (list of ISO2), ``role`` (title
    substring, case-insensitive) and ``sponsorship`` (bool). An empty
    filter set matches everything.
    """
    countries = [c.upper() for c in (filters.get("countries") or [])]
    if countries and str(job.get("country") or "").upper() not in countries:
        return False
    role = str(filters.get("role") or "").strip()
    if role and role.casefold() not in str(job.get("title") or "").casefold():
        return False
    return not (filters.get("sponsorship") is True and not job.get("visa_sponsorship"))


def create_alert(
    user_id: str,
    filters: dict[str, Any] | None = None,
    *,
    frequency: str = "daily",
) -> dict[str, Any]:
    """Save a search alert (task 15.9 §13.2 POST)."""
    if not user_id:
        raise VantiaError("user_id is required", code="user_id_required")
    frequency = _validate_frequency(frequency)
    with _store_lock:
        data = _load_all()
        alert_id = _new_id(user_id)
        now = utc_now()
        row = {
            "id": alert_id,
            "user_id": user_id,
            "filters": filters or {},
            "frequency": frequency,
            "last_sent_at": None,
            "active": True,
            "created_at": now,
        }
        data["alerts"][alert_id] = row
        _save_all(data)
    return row


def alerts_for(user_id: str) -> list[dict[str, Any]]:
    """All alerts for one user, newest first."""
    rows = [r for r in _load_all()["alerts"].values() if r.get("user_id") == user_id]
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows


def list_alerts(user_id: str) -> list[dict[str, Any]]:
    """All alerts for one user (task 15.9 §13.2 GET)."""
    return alerts_for(user_id)


def delete_alert(user_id: str, alert_id: str) -> bool:
    """Remove an alert the user owns (task 15.9 §13.2 DELETE)."""
    with _store_lock:
        data = _load_all()
        row = data["alerts"].get(alert_id)
        if row is None or row.get("user_id") != user_id:
            raise VantiaError(f"alert {alert_id!r} not found", code="alert_not_found")
        del data["alerts"][alert_id]
        _save_all(data)
    return True


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts)
    except ValueError:
        return None
    # Normalise naive (date-only ``YYYY-MM-DD``) stamps to UTC-aware so
    # window comparisons never mix naive and aware datetimes.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def due_alerts(now: datetime | None = None) -> list[dict[str, Any]]:
    """Active alerts whose digest window has elapsed since ``last_sent_at``.

    An alert never sent (``last_sent_at`` None) is always due — the first
    digest goes out immediately.
    """
    current = now or datetime.now(UTC)
    due: list[dict[str, Any]] = []
    for row in _load_all()["alerts"].values():
        if not row.get("active", True):
            continue
        last = _parse(row.get("last_sent_at"))
        if last is None:
            due.append(row)
            continue
        if current - last >= INTERVAL.get(row.get("frequency", "daily"), INTERVAL["daily"]):
            due.append(row)
    return due


def jobs_since(
    alert: dict[str, Any], jobs: list[dict[str, Any]], *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """New jobs for one alert: matching filters, posted since last digest.

    Excludes anything posted before ``last_sent_at`` (so a re-run in the
    same window sends nothing twice — R no-duplicate-emails). Sorted newest
    first; caller takes the top 5.
    """
    current = now or datetime.now(UTC)
    last = _parse(alert.get("last_sent_at"))
    filters = alert.get("filters") or {}
    out: list[dict[str, Any]] = []
    for job in jobs:
        if not matches_filters(job, filters):
            continue
        posted = _parse(str(job.get("posted_at") or ""))
        if last is not None and posted is not None and posted <= last:
            continue
        if posted is not None and posted > current:
            continue
        out.append(job)
    out.sort(key=lambda j: str(j.get("posted_at") or ""), reverse=True)
    return out


def mark_sent(alert_id: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    """Stamp ``last_sent_at`` after a digest is dispatched (idempotency)."""
    with _store_lock:
        data = _load_all()
        row = data["alerts"].get(alert_id)
        if row is None:
            return None
        row["last_sent_at"] = (now or datetime.now(UTC)).isoformat()
        _save_all(data)
    return row
