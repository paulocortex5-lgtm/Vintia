"""Application tracker (task 15.8).

A per-user kanban of applications: every card snapshots the job at the
moment it was tracked, so the history survives even if the original
listing is later removed from search (dead link, expired, rejected).

Design (repo rules carried over):

* **Local-first / git-authoritative** — ``.vantia/applications/applications.json``
  is the source of truth; a Supabase mirror is best-effort, never raising.
* **Snapshot on create** — ``job_snapshot`` freezes the listing fields the
  card renders (title, company, country, apply_url, posted date) so the
  board is stable and auditable.
* **Status vocabulary** is fixed (§12.1): applied, interview, offer,
  rejected, withdrawn — anything else is refused, never silently coerced.
* **Owner isolation (R26)** — every row carries ``owner_id``; reads and
  writes are scoped to it. No cross-user reads are possible by construction.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from typing import Any

from ..errors import VantiaError
from ..json_utils import atomic_write_json, load_json
from ..logging_config import utc_now

__all__ = [
    "APPLICATION_STATUSES",
    "applications_for",
    "counts_for",
    "create_application",
    "delete_application",
    "list_applications",
    "update_application",
]

LOGGER = logging.getLogger("vantia.applications.tracker")

STORE_VERSION = 1

#: §12.1 status vocabulary (kanban columns).
APPLICATION_STATUSES = ("applied", "interview", "offer", "rejected", "withdrawn")

_store_lock = threading.RLock()


def _default_dir() -> str:
    return os.environ.get("VANTIA_APPLICATIONS_DIR", os.path.join(".vantia", "applications"))


def _store_file() -> str:
    return os.path.join(_default_dir(), "applications.json")


def _load_all() -> dict[str, Any]:
    data = load_json(_store_file())
    if not isinstance(data, dict) or not isinstance(data.get("applications"), dict):
        return {"version": STORE_VERSION, "applications": {}}
    return data


def _save_all(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_store_file()), exist_ok=True)
    atomic_write_json(_store_file(), data)


def _validate_status(status: str) -> str:
    if status not in APPLICATION_STATUSES:
        raise VantiaError(
            f"unknown status {status!r}; known: {', '.join(APPLICATION_STATUSES)}",
            code="invalid_status",
        )
    return status


def _snapshot(job: dict[str, Any]) -> dict[str, Any]:
    """Freeze the fields the card renders; ignore everything else."""
    return {
        "job_id": str(job.get("id") or job.get("job_id") or ""),
        "title": str(job.get("title") or "Untitled role"),
        "company": str(job.get("company") or job.get("employer") or "—"),
        "country": str(job.get("country") or ""),
        "location": str(job.get("location") or ""),
        "apply_url": str(job.get("apply_url") or ""),
        "link_status": str(job.get("link_status") or ""),
        "posted_at": str(job.get("posted_at") or ""),
        "sponsor_company": str(job.get("company") or job.get("employer") or ""),
    }


def _new_id(owner_id: str, job_id: str) -> str:
    seed = f"{owner_id}:{job_id}:{utc_now()}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def create_application(
    owner_id: str,
    job_id: str,
    *,
    job: dict[str, Any] | None = None,
    notes: str = "",
    status: str = "applied",
) -> dict[str, Any]:
    """Track one job (task 15.8 §12.2 POST). Idempotent per (owner, job_id).

    Re-tracking the same job returns the existing card rather than creating
    a duplicate; a fresh job is snapshotted and appended.
    """
    if not owner_id:
        raise VantiaError("owner_id is required", code="owner_id_required")
    if not job_id:
        raise VantiaError("job_id is required", code="job_id_required")
    status = _validate_status(status)

    with _store_lock:
        data = _load_all()
        rows = data["applications"]
        for existing in rows.values():
            if existing.get("owner_id") == owner_id and existing.get("job_id") == job_id:
                return existing
        app_id = _new_id(owner_id, job_id)
        now = utc_now()
        row = {
            "id": app_id,
            "owner_id": owner_id,
            "job_id": job_id,
            "job_snapshot": _snapshot(job or {"id": job_id, "job_id": job_id}),
            "status": status,
            "notes": notes[:2000],
            "applied_at": now,
            "updated_at": now,
        }
        rows[app_id] = row
        _save_all(data)
    return row


def applications_for(owner_id: str) -> list[dict[str, Any]]:
    """All applications for one owner, newest-updated first."""
    rows = [row for row in _load_all()["applications"].values() if row.get("owner_id") == owner_id]
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return rows


def list_applications(owner_id: str, *, status: str | None = None) -> list[dict[str, Any]]:
    """Applications for one owner, optionally filtered by column status."""
    if status:
        status = _validate_status(status)
    return [r for r in applications_for(owner_id) if not status or r.get("status") == status]


def counts_for(owner_id: str) -> dict[str, int]:
    """Live per-column counts for the kanban header (§12.4)."""
    counts = {s: 0 for s in APPLICATION_STATUSES}
    for row in applications_for(owner_id):
        s = str(row.get("status") or "applied")
        counts[s] = counts.get(s, 0) + 1
    counts["total"] = sum(counts[s] for s in APPLICATION_STATUSES)
    return counts


def update_application(
    owner_id: str,
    app_id: str,
    *,
    status: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Move a card between columns / edit notes (task 15.8 §12.2 PATCH)."""
    if status is not None:
        status = _validate_status(status)
    with _store_lock:
        data = _load_all()
        row = data["applications"].get(app_id)
        if row is None or row.get("owner_id") != owner_id:
            raise VantiaError(f"application {app_id!r} not found", code="application_not_found")
        if status is not None:
            row["status"] = status
        if notes is not None:
            row["notes"] = notes[:2000]
        row["updated_at"] = utc_now()
        _save_all(data)
    return row


def delete_application(owner_id: str, app_id: str) -> bool:
    """Remove a card the user owns (task 15.8 §12.2 DELETE)."""
    with _store_lock:
        data = _load_all()
        row = data["applications"].get(app_id)
        if row is None or row.get("owner_id") != owner_id:
            raise VantiaError(f"application {app_id!r} not found", code="application_not_found")
        del data["applications"][app_id]
        _save_all(data)
    return True
