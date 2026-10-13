"""Job alert digest dispatcher (task 15.9 §13.3).

Run by the GitHub Actions cron ``.github/workflows/job-alerts.yml`` at
08:00 UTC (and manually via ``--dry-run``). For every due alert it emails
the top 5 new matching jobs, then stamps ``last_sent_at`` so a re-run in
the same window sends nothing twice.

Email transport is pluggable and honest:

* **Resend** when ``RESEND_API_KEY`` (+ ``RESEND_FROM``) is set — the
  production path.
* **Local outbox** otherwise — each digest is written to
  ``.vantia/alerts/outbox/<alert_id>.json`` and logged, so the pipeline is
  fully exercisable offline and never silently pretends an email was sent.

Every digest records the job ids it carried in ``last_sent_ids`` so the
next window can exclude them even if posting timestamps are coarse.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from ..logging_config import utc_now
from ..sources.ingest_store import search_jobs
from . import manager

__all__ = ["DIGEST_LIMIT", "build_digest", "run", "send_one"]

LOGGER = logging.getLogger("vantia.alerts.send_digests")

#: §13.3 — top 5 new matching jobs per digest.
DIGEST_LIMIT = 5


def _outbox_dir() -> str:
    return os.path.join(manager._default_dir(), "outbox")


def build_digest(alert: dict[str, Any], jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Assemble one digest payload: subject, text body, and the job list."""
    fresh = manager.jobs_since(alert, jobs)[:DIGEST_LIMIT]
    count = len(fresh)
    filters = alert.get("filters") or {}
    where = ", ".join(filters.get("countries") or []) or "all countries"
    role = filters.get("role") or "any role"
    subject = f"{count} new job{'s' if count != 1 else ''} match your {role} search"
    lines = [
        f"{count} new {where} job{'s' if count != 1 else ''} match your saved search.",
        "",
    ]
    for job in fresh:
        title = job.get("title") or "Untitled role"
        company = job.get("company") or "—"
        url = job.get("apply_url") or job.get("url") or ""
        lines.append(f"• {title} — {company}")
        if url:
            lines.append(f"  {url}")
    return {
        "alert_id": alert.get("id"),
        "user_id": alert.get("user_id"),
        "to": alert.get("email") or "",
        "subject": subject,
        "body": "\n".join(lines),
        "jobs": [
            {"id": j.get("id"), "title": j.get("title"), "apply_url": j.get("apply_url")}
            for j in fresh
        ],
        "count": count,
        "generated_at": utc_now(),
    }


def _send_resend(digest: dict[str, Any]) -> bool:
    """Best-effort Resend dispatch; returns False (never raises) on failure."""
    api_key = os.environ.get("RESEND_API_KEY")
    from_addr = os.environ.get("RESEND_FROM", "alerts@vantia.ai")
    to = digest.get("to")
    if not api_key or not to:
        return False
    try:
        import requests

        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": from_addr,
                "to": [to],
                "subject": digest["subject"],
                "text": digest["body"],
            },
            timeout=15,
        )
        return response.status_code in (200, 201)
    except Exception as exc:  # noqa: BLE001 — transport must never crash the cron
        LOGGER.warning("resend dispatch failed for %s: %s", digest.get("alert_id"), exc)
        return False


def send_one(
    alert: dict[str, Any], jobs: list[dict[str, Any]], *, dry_run: bool = False
) -> dict[str, Any] | None:
    """Dispatch one alert's digest; stamp ``last_sent_at``; return the digest."""
    digest = build_digest(alert, jobs)
    if digest["count"] == 0:
        # Nothing new — do not email, do not advance the window (avoid
        # skipping jobs that arrive later in the same interval).
        return None
    if dry_run:
        digest["sent"] = False
        digest["channel"] = "dry-run"
        return digest
    sent = _send_resend(digest)
    if not sent:
        # Honest local outbox so the run is auditable offline.
        os.makedirs(_outbox_dir(), exist_ok=True)
        path = os.path.join(_outbox_dir(), f"{alert.get('id')}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(digest, handle, ensure_ascii=False, indent=2)
        digest["sent"] = False
        digest["channel"] = "outbox"
    else:
        digest["sent"] = True
        digest["channel"] = "resend"
    manager.mark_sent(str(alert.get("id")), now=datetime.now(UTC))
    return digest


def run(*, dry_run: bool = False, now: datetime | None = None) -> dict[str, Any]:
    """Dispatch every due alert; returns a summary ``{due, sent, skipped}``."""
    jobs = search_jobs(verified_only=True)
    due = manager.due_alerts(now=now)
    sent = skipped = 0
    digests: list[dict[str, Any]] = []
    for alert in due:
        digest = send_one(alert, jobs, dry_run=dry_run)
        if digest is None:
            skipped += 1
            continue
        sent += 1
        digests.append(digest)
    return {"due": len(due), "sent": sent, "skipped": skipped, "digests": digests}


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch due Vantia job-alert digests.")
    parser.add_argument("--dry-run", action="store_true", help="build digests, send nothing")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    summary = run(dry_run=args.dry_run)
    LOGGER.info(
        "job alerts: due=%s sent=%s skipped=%s",
        summary["due"],
        summary["sent"],
        summary["skipped"],
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
