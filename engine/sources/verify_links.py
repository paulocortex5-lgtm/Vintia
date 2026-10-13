"""Direct application link verification (task 15.2).

Every stored job must carry a **verified direct application link** pointing
at the employer's own careers portal or a known ATS platform — never a
recruiter, aggregator or other middleman. Links are re-verified on a
6-hour freshness cycle; expired links are marked and hidden from search.

Checks, in order (§6.2):

1. **HTTPS-only** — plain HTTP is rejected.
2. **Domain check** — the apply URL's domain must be the company's own
   domain (as recorded at ingestion) or a known ATS portal domain.
3. **Middleman check** — a domain that is neither the company's nor a
   known ATS is rejected (never downranked quietly).
4. **Reachability** — a HEAD request must return 200. 404/410/451 mark the
   link *expired*; other non-200s mark it *stale* for the next cycle.
5. **Fee-language check** — the posting description is run through the
   predatory-enforcement fee patterns (:mod:`engine.security.predatory`).

The HEAD function is injectable (``head_fn(url) -> int``) so tests never
touch the network; the default uses ``httpx`` with a short timeout.

CLI (used by the ``verify-links`` GitHub Actions cron)::

    python -m engine.sources.verify_links --batch-size 500
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from ..security.predatory import matches_fee_language
from .ingest_store import (
    LINK_STATUS_EXPIRED,
    LINK_STATUS_REJECTED,
    LINK_STATUS_STALE,
    LINK_STATUS_VERIFIED,
    JobRecord,
    jobs_needing_verification,
    upsert,
)

__all__ = [
    "KNOWN_ATS_DOMAINS",
    "LINK_FRESHNESS_HOURS",
    "LinkCheck",
    "apply_domain",
    "check_link",
    "is_known_ats",
    "verify_batch",
]

LOGGER = logging.getLogger("vantia.sources.verify_links")

#: Known ATS / job-portal platforms whose apply URLs are employer-direct (§6.2).
KNOWN_ATS_DOMAINS: frozenset[str] = frozenset(
    {
        "greenhouse.io",
        "lever.co",
        "myworkdayjobs.com",
        "successfactors.com",
        "icims.com",
        "smartrecruiters.com",
        "workable.com",
    }
)

#: Links older than this must be re-verified (§6.2 rule 6).
LINK_FRESHNESS_HOURS = 6

#: HTTP statuses that mean the listing is gone (not a transient fault).
DEAD_STATUSES: frozenset[int] = frozenset({404, 410, 451})

HeadFn = Callable[[str], int]


def _default_head(url: str) -> int:
    """HEAD request via httpx; any transport failure → 0 (treated as stale)."""
    import httpx

    try:
        response = httpx.head(url, timeout=10.0, follow_redirects=True)
        return response.status_code
    except httpx.HTTPError:
        return 0


def apply_domain(url: str) -> str:
    """Lowercased registrable host of ``url`` (``""`` when unparseable)."""
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_known_ats(domain: str) -> bool:
    """True when ``domain`` is, or is a subdomain of, a known ATS platform."""
    host = domain.lower().rstrip(".")
    return any(host == ats or host.endswith("." + ats) for ats in KNOWN_ATS_DOMAINS)


def check_link(
    record: dict[str, Any] | JobRecord,
    *,
    head_fn: HeadFn | None = None,
    now: datetime | None = None,
) -> LinkCheck:
    """Run the five §6.2 checks against one record's ``apply_url``.

    Deterministic: the only network touch is ``head_fn`` (injectable).
    """
    data = record.to_dict() if isinstance(record, JobRecord) else record
    checked_at = (now or datetime.now(UTC)).isoformat()
    apply_url = (data.get("apply_url") or "").strip()

    if not apply_url:
        return LinkCheck(LINK_STATUS_REJECTED, "no_apply_url", checked_at)
    if not apply_url.lower().startswith("https://"):
        return LinkCheck(LINK_STATUS_REJECTED, "not_https", checked_at)

    domain = apply_domain(apply_url)
    company_domain = (data.get("company_domain") or "").lower().rstrip(".")
    if not domain:
        return LinkCheck(LINK_STATUS_REJECTED, "unparseable_url", checked_at)

    # Rules 2 + 5 — domain must be the company's own or a known ATS.
    domain_ok = bool(company_domain) and (
        domain == company_domain or domain.endswith("." + company_domain) or is_known_ats(domain)
    )
    if not domain_ok:
        return LinkCheck(
            LINK_STATUS_REJECTED,
            f"middleman_or_mismatch:{domain}",
            checked_at,
        )

    # Rule 4 — reachability.
    head = head_fn or _default_head
    code = head(apply_url)
    if code in DEAD_STATUSES:
        return LinkCheck(LINK_STATUS_EXPIRED, f"dead_status:{code}", checked_at)
    if code != 200:
        return LinkCheck(LINK_STATUS_STALE, f"unreachable:{code}", checked_at)

    # Rule 5 — fee language in the description is predatory.
    if matches_fee_language(data.get("description") or ""):
        return LinkCheck(LINK_STATUS_REJECTED, "fee_language", checked_at)

    return LinkCheck(LINK_STATUS_VERIFIED, "ok", checked_at)


def verify_batch(
    batch_size: int = 500,
    *,
    store_dir: str | None = None,
    head_fn: HeadFn | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Verify unverified links first, then links older than 6 hours (§6.4).

    Updates every processed record in the ingest store with its new
    ``link_status`` / ``link_checked_at`` / ``link_expires_at`` /
    ``link_status_reason``. Returns per-status counts.
    """
    current = now or datetime.now(UTC)
    batch = jobs_needing_verification(
        store_dir=store_dir,
        max_age_hours=LINK_FRESHNESS_HOURS,
        batch_size=batch_size,
        now=current,
    )
    counts = {"checked": 0, "verified": 0, "expired": 0, "rejected": 0, "stale": 0}
    expires_at = (current + timedelta(hours=LINK_FRESHNESS_HOURS)).isoformat()

    for data in batch:
        record = JobRecord.from_dict(data)
        result = check_link(record, head_fn=head_fn, now=current)
        record.link_status = result.status
        record.link_checked_at = result.checked_at
        record.link_expires_at = expires_at if result.status == LINK_STATUS_VERIFIED else None
        record.link_status_reason = result.reason
        upsert(record, store_dir=store_dir)
        counts["checked"] += 1
        counts[result.status] = counts.get(result.status, 0) + 1
        LOGGER.info(
            "link verified",
            extra={
                "record_id": record.id,
                "link_status": result.status,
                "reason": result.reason,
            },
        )
    return counts


def main(argv: list[str] | None = None) -> int:
    """CLI entry for the ``verify-links`` cron workflow (§6.5)."""
    parser = argparse.ArgumentParser(description="Verify stored job apply links")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--store-dir", default=None)
    args = parser.parse_args(argv)
    counts = verify_batch(args.batch_size, store_dir=args.store_dir)
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised by the cron only
    sys.exit(main())


@dataclass(frozen=True)
class LinkCheck:
    """Outcome of verifying one apply URL."""

    status: str  # verified | expired | rejected | stale
    reason: str
    checked_at: str

    def to_dict(self) -> dict[str, str]:
        return {"status": self.status, "reason": self.reason, "checked_at": self.checked_at}
