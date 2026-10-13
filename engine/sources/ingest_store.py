"""Job ingest store (task 15.2) — local-first records with link-verification state.

The platform fetches jobs live from portal and government adapters; there is
no server-side job database in this deployment. The ingest store is the
durable, git-authoritative record layer *around* those listings: every
listing that passes through verification and anti-predatory enforcement
(:mod:`engine.sources.verify_links`, :mod:`engine.security.predatory`) is
upserted here with its ``apply_url`` state, so search, recommendations
(:mod:`engine.ats.recommender`) and the status page read one consistent,
auditable source.

Design (repo rules carried over):

* **Local-first / git-authoritative** — ``$VANTIA_INGEST_DIR/jobs.json``
  (default ``.vantia/ingest/``) is the source of truth, mirroring every
  other ``.vantia/`` store; a Supabase mirror is best-effort, never raising.
* **Stable identity** — one record per ``{portal}:{external_id}``; re-ingest
  upserts and never duplicates.
* **Append-only rejection audit** — rejected postings are copied to
  ``rejected_jobs.json`` with a machine-readable ``reason_code`` and the
  original payload (task 15.3); nothing is edited or deleted there.
* **Thread-safe, atomic writes** — one re-entrant lock; writes go through
  :func:`engine.json_utils.atomic_write_json`.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ..json_utils import atomic_write_json, load_json
from ..logging_config import utc_now

__all__ = [
    "INGEST_VERSION",
    "LINK_STATUSES",
    "LINK_STATUS_EXPIRED",
    "LINK_STATUS_REJECTED",
    "LINK_STATUS_STALE",
    "LINK_STATUS_UNVERIFIED",
    "LINK_STATUS_VERIFIED",
    "JobRecord",
    "append_rejected",
    "default_store",
    "jobs_needing_verification",
    "load_jobs",
    "load_rejected",
    "record_id",
    "save_jobs",
    "search_jobs",
    "upsert",
    "upsert_many",
]

LOGGER = logging.getLogger("vantia.sources.ingest_store")

INGEST_VERSION = 1

#: link_status vocabulary (task 15.2 §6.3).
LINK_STATUS_UNVERIFIED = "unverified"
LINK_STATUS_VERIFIED = "verified"
LINK_STATUS_EXPIRED = "expired"
LINK_STATUS_REJECTED = "rejected"
LINK_STATUS_STALE = "stale"

LINK_STATUSES = (
    LINK_STATUS_UNVERIFIED,
    LINK_STATUS_VERIFIED,
    LINK_STATUS_EXPIRED,
    LINK_STATUS_REJECTED,
    LINK_STATUS_STALE,
)

_store_lock = threading.RLock()


def _default_dir() -> str:
    return os.environ.get("VANTIA_INGEST_DIR", os.path.join(".vantia", "ingest"))


def _jobs_path(store_dir: str | None = None) -> str:
    return os.path.join(store_dir or _default_dir(), "jobs.json")


def _rejected_path(store_dir: str | None = None) -> str:
    return os.path.join(store_dir or _default_dir(), "rejected_jobs.json")


def record_id(portal: str, external_id: str) -> str:
    """Stable identity of one ingested posting."""
    return f"{portal}:{external_id}"


@dataclass
class JobRecord:
    """One ingested posting plus its verification and enforcement state.

    Carries the :class:`engine.sources.portals.base.JobListing` core fields
    plus the task-15.2 link-verification columns (``apply_url``,
    ``apply_url_domain``, ``link_status``, ``link_checked_at``,
    ``link_expires_at``, ``link_status_reason``) so one record round-trips
    through JSON losslessly.
    """

    portal: str
    external_id: str
    title: str
    company: str
    url: str
    location: str = ""
    country: str = ""  # ISO 3166-1 alpha-2, "" when unknown
    posted_at: str | None = None  # YYYY-MM-DD
    closes_at: str | None = None  # YYYY-MM-DD
    description: str = ""
    visa_sponsorship: bool | None = None
    # Task 15.2 — direct application link verification.
    apply_url: str = ""
    apply_url_domain: str = ""
    company_domain: str = ""  # employer's own domain when known
    link_status: str = LINK_STATUS_UNVERIFIED
    link_checked_at: str | None = None  # ISO timestamp
    link_expires_at: str | None = None  # ISO timestamp (checked_at + 6h)
    link_status_reason: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return record_id(self.portal, self.external_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobRecord:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})


def load_jobs(store_dir: str | None = None) -> dict[str, dict[str, Any]]:
    """All records keyed by ``record_id``; absent file → empty store."""
    data = load_json(_jobs_path(store_dir))
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), dict):
        return {}
    return data["jobs"]


def save_jobs(jobs: dict[str, dict[str, Any]], store_dir: str | None = None) -> str:
    """Persist the full job map atomically."""
    path = _jobs_path(store_dir)
    payload = {"version": INGEST_VERSION, "jobs": jobs, "saved_at": utc_now()}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_json(path, payload)
    return path


def upsert(record: JobRecord, store_dir: str | None = None) -> dict[str, Any]:
    """Insert or update one record by id; returns the stored dict."""
    with _store_lock:
        jobs = load_jobs(store_dir)
        jobs[record.id] = record.to_dict()
        save_jobs(jobs, store_dir)
    return jobs[record.id]


def upsert_many(records: list[JobRecord], store_dir: str | None = None) -> int:
    """Batch upsert; returns how many records are now stored."""
    with _store_lock:
        jobs = load_jobs(store_dir)
        for record in records:
            jobs[record.id] = record.to_dict()
        save_jobs(jobs, store_dir)
    return len(jobs)


def jobs_needing_verification(
    *,
    store_dir: str | None = None,
    max_age_hours: int = 6,
    batch_size: int = 500,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Unverified records first, then records checked more than
    ``max_age_hours`` ago (task 15.2 freshness rule), capped at ``batch_size``.
    """
    current = now or datetime.now(UTC)
    cutoff = current - timedelta(hours=max_age_hours)
    jobs = load_jobs(store_dir)

    unverified: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    for record in jobs.values():
        status = record.get("link_status", LINK_STATUS_UNVERIFIED)
        if status == LINK_STATUS_UNVERIFIED:
            unverified.append(record)
            continue
        checked = record.get("link_checked_at")
        try:
            checked_at = datetime.fromisoformat(checked) if checked else None
        except ValueError:
            checked_at = None
        if checked_at is None or checked_at < cutoff:
            stale.append(record)

    key = lambda r: str(r.get("id") or r.get("external_id") or "")
    unverified.sort(key=key)
    stale.sort(key=key)
    return (unverified + stale)[:batch_size]


def search_jobs(
    *,
    store_dir: str | None = None,
    country: str | None = None,
    role: str | None = None,
    verified_only: bool = True,
    active_only: bool = True,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Search stored jobs; verified-only by default (rejected/expired never surface).

    ``role`` is a case-insensitive substring match against the title.
    """
    current = today or datetime.now(UTC).date()
    results: list[dict[str, Any]] = []
    for record in load_jobs(store_dir).values():
        if verified_only and record.get("link_status") != LINK_STATUS_VERIFIED:
            continue
        if country and (record.get("country") or "").upper() != country.upper():
            continue
        if role and role.casefold() not in (record.get("title") or "").casefold():
            continue
        closes = record.get("closes_at")
        if active_only and closes:
            try:
                if date.fromisoformat(closes) < current:
                    continue
            except ValueError:
                pass
        results.append(record)
    results.sort(key=lambda r: r.get("posted_at") or "", reverse=True)
    return results


def append_rejected(
    *,
    source: str,
    external_id: str,
    reason_code: str,
    payload: dict[str, Any],
    reason_detail: str = "",
    store_dir: str | None = None,
) -> dict[str, Any]:
    """Append one rejection to the append-only audit file (task 15.3 §7.3).

    Deduplicated by ``(source, external_id, reason_code)``: re-enforcement of
    the same posting logs once — the audit trail never spams itself.
    """
    with _store_lock:
        path = _rejected_path(store_dir)
        data = load_json(path)
        if not isinstance(data, dict) or not isinstance(data.get("rejected"), list):
            data = {"version": INGEST_VERSION, "rejected": []}
        for entry in data["rejected"]:
            if (
                entry.get("source") == source
                and entry.get("external_id") == external_id
                and entry.get("reason_code") == reason_code
            ):
                return entry
        entry = {
            "source": source,
            "external_id": external_id,
            "reason_code": reason_code,
            "reason_detail": reason_detail,
            "payload": payload,
            "rejected_at": utc_now(),
        }
        data["rejected"].append(entry)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_write_json(path, data)
    return entry


def load_rejected(store_dir: str | None = None) -> list[dict[str, Any]]:
    """All rejection audit entries (empty list when absent)."""
    data = load_json(_rejected_path(store_dir))
    if not isinstance(data, dict) or not isinstance(data.get("rejected"), list):
        return []
    return data["rejected"]


def default_store() -> str:
    """The resolved default store directory (for status pages / CLIs)."""
    return _default_dir()
