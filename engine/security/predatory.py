"""Anti-predatory enforcement (task 15.3).

Deterministic, provider-free rejection of predatory postings **before** they
enter the ingest store or any search result. A posting is rejected — never
shown, never downranked quietly — when any rule in §7.1 fires:

1. ``fee_language``    — any of the 12 fee patterns matches the description
2. ``unverified_link`` — the apply URL is not in ``verified`` state
3. ``domain_mismatch`` — posting company ≠ apply domain (unless a known ATS)
4. ``scam_aggregator`` — posting or apply domain is on the maintained list
5. ``injection_detected`` — prompt-injection corpus fires at block strength
6. ``pii_request``     — asks the candidate to send money, IDs or passport
                         scans to an email / messaging app

Every rejection is appended to the ingest store's append-only audit file
(:func:`engine.sources.ingest_store.append_rejected`) with the original
payload, so a human can always answer "why was this blocked?".

The scam-aggregator list ships as a data file
(``engine/security/data/scam_aggregators.txt``) seeded from published
threat research (DomainTools *Fake Job Boards*, Nov 2024); it is loaded on
import and reloaded by :func:`load_scam_list` whenever the file changes.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from .injection import assess_injection

__all__ = [
    "FEE_PATTERNS",
    "PII_REQUEST_PATTERNS",
    "PREDATORY_REASON_CODES",
    "PredatoryVerdict",
    "enforce",
    "evaluate",
    "load_scam_list",
    "matches_fee_language",
    "matches_pii_request",
]

LOGGER = logging.getLogger("vantia.security.predatory")

#: Machine-readable rejection reason codes (§7.3).
PREDATORY_REASON_CODES = (
    "fee_language",
    "unverified_link",
    "domain_mismatch",
    "scam_aggregator",
    "injection_detected",
    "pii_request",
)

_FEE_RE = re.compile

# ── Rule 1 — the 12 fee patterns ─────────────────────────────────────────
FEE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "pay_interview_visa_fee",
        _FEE_RE(r"pay (a |an )?(interview|visa|application|processing|registration|document) fee"),
    ),
    (
        "candidate_must_pay",
        _FEE_RE(
            r"(candidates?|applicants?|job ?seekers?|you) (must|will|shall|has to) pay (a |an )?fee"
        ),
    ),
    (
        "fee_payable_by_candidate",
        _FEE_RE(
            r"(fee|amount|deposit) (payable|to be paid|to pay) (by|from|toward|towards)"
            r" (the )?(candidate|applicant|you)"
        ),
    ),
    (
        "salary_deduction",
        _FEE_RE(
            r"(deduct|deduction of) (the )?(fee|salary|amount|deduction) (from|out of)"
            r"|salary (will be )?deducted"
        ),
    ),
    (
        "refundable_fee",
        _FEE_RE(r"refundable (fee|deposit)|deposit (is |to be )?refundable"),
    ),
    (
        "processing_fee_amount",
        _FEE_RE(r"(usd|eur|gbp|£|€|\$)\s?\d+.*(processing|application|registration|service) fee"),
    ),
    (
        "money_transfer_service",
        _FEE_RE(r"western union|moneygram|remitly|ria money transfer"),
    ),
    (
        "visa_appointment_fee",
        _FEE_RE(r"fee (for|to) (book|schedule|secure) (your )?(visa|interview|appointment)"),
    ),
    (
        "gift_card_payment",
        _FEE_RE(r"pay(ment)? (via|by|through) (a )?gift ?card"),
    ),
    (
        "pre_hiring_transfer",
        _FEE_RE(r"bank transfer (before|prior to|ahead of) (the )?(interview|hiring|joining)"),
    ),
    (
        "crypto_payment",
        _FEE_RE(r"pay(ment)? (via|in|through) (crypto|bitcoin|btc|eth|usdt|usdc)"),
    ),
    (
        "mandatory_extra_fees",
        _FEE_RE(
            r"(training|uniform|equipment|kit|insurance|documentation) fee"
            r" (is |are )?(mandatory|required|compulsory|payable)"
        ),
    ),
)

# ── Rule 6 — PII / money requests ────────────────────────────────────────
PII_REQUEST_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "send_passport",
        _FEE_RE(r"send (us )?(a |your |the )?(scan|copy|photo|image)? ?(of )?(your )?passport"),
    ),
    (
        "email_id",
        _FEE_RE(
            r"(email|e-mail|whatsapp|telegram|sms) (us )?(your )?(id|identity|passport|national id)"
            r"|(your )?(id|identity|passport|national id) (via|through|on|over)"
            r" (whatsapp|telegram|sms|email|e-mail)"
        ),
    ),
    (
        "passport_number",
        _FEE_RE(r"(provide|supply|share) (us )?(your )?passport (number|no\.?)"),
    ),
    (
        "western_union_request",
        _FEE_RE(r"western union|moneygram"),
    ),
    (
        "copy_of_id",
        _FEE_RE(r"(scan|copy|photo) of (your )?(id|identity document|identification)"),
    ),
    (
        "bank_details_request",
        _FEE_RE(r"(share|send|provide) (us )?(your )?bank (details|account|account number)"),
    ),
)

_SCAM_LIST_PATH = os.path.join(os.path.dirname(__file__), "data", "scam_aggregators.txt")

_scam_cache: frozenset[str] | None = None
_scam_cache_mtime: float | None = None


def load_scam_list(path: str | None = None) -> frozenset[str]:
    """Load the maintained scam-aggregator domain list.

    The file is ``#``-commented, one domain (or parent suffix) per line.
    Cached by mtime — a change to the file is picked up on the next call.
    """
    global _scam_cache, _scam_cache_mtime
    resolved = path or _SCAM_LIST_PATH
    try:
        mtime = os.stat(resolved).st_mtime
    except OSError:
        return _scam_cache or frozenset()
    if _scam_cache is not None and _scam_cache_mtime == mtime:
        return _scam_cache
    entries: set[str] = set()
    with open(resolved, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                entries.add(line.lower().lstrip("."))
    _scam_cache = frozenset(entries)
    _scam_cache_mtime = mtime
    return _scam_cache


def _matches_scam_list(domain: str) -> str | None:
    """Return the matching scam-list entry for ``domain``, or None."""
    host = domain.lower().rstrip(".")
    if not host:
        return None
    for entry in load_scam_list():
        if host == entry or host.endswith("." + entry):
            return entry
    return None


def matches_fee_language(text: str) -> bool:
    """True when any of the 12 fee patterns fires on ``text``."""
    lowered = text.casefold()
    return any(pattern.search(lowered) for _, pattern in FEE_PATTERNS)


def matches_pii_request(text: str) -> bool:
    """True when any PII/money-request pattern fires on ``text``."""
    lowered = text.casefold()
    return any(pattern.search(lowered) for _, pattern in PII_REQUEST_PATTERNS)


@dataclass(frozen=True)
class PredatoryVerdict:
    """Outcome of evaluating one posting against every §7.1 rule."""

    rejected: bool
    reason_code: str  # "" when accepted
    reason_detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rejected": self.rejected,
            "reason_code": self.reason_code,
            "reason_detail": self.reason_detail,
        }


_ACCEPT = PredatoryVerdict(rejected=False, reason_code="")


def _first_fee_pattern(text: str) -> tuple[str, str] | None:
    """Return (name, matched_text) for the first fee pattern that fires."""
    lowered = text.casefold()
    for name, pattern in FEE_PATTERNS:
        match = pattern.search(lowered)
        if match:
            return name, match.group(0)
    return None


def _first_pii_pattern(text: str) -> tuple[str, str] | None:
    lowered = text.casefold()
    for name, pattern in PII_REQUEST_PATTERNS:
        match = pattern.search(lowered)
        if match:
            return name, match.group(0)
    return None


def evaluate(record: dict[str, Any] | Any) -> PredatoryVerdict:
    """Evaluate one posting against every §7.1 rejection rule.

    Order of checks (first match wins): fee language → PII request →
    injection → scam aggregator → unverified/middleman link. ``record`` is
    any dict (or :class:`~engine.sources.ingest_store.JobRecord`) with
    ``title``, ``description``, ``apply_url``, ``link_status`` and
    ``company_domain`` keys.
    """
    data = record.to_dict() if hasattr(record, "to_dict") else dict(record)
    description = f"{data.get('title', '')} {data.get('description', '')}"

    # Rule 1 — fee language.
    fee = _first_fee_pattern(description)
    if fee:
        return PredatoryVerdict(True, "fee_language", f"pattern={fee[0]} match={fee[1]!r}")

    # Rule 6 — PII / money requests.
    pii = _first_pii_pattern(description)
    if pii:
        return PredatoryVerdict(True, "pii_request", f"pattern={pii[0]} match={pii[1]!r}")

    # Rule 5 — prompt injection at block strength.
    injection = assess_injection(description)
    if injection.blocked:
        return PredatoryVerdict(True, "injection_detected", f"score={injection.score:.1f}")

    # Local import — avoids a module-level cycle with verify_links.
    from ..sources.verify_links import apply_domain, is_known_ats

    # Rule 4 — known scam aggregator domain.
    apply_url = data.get("apply_url") or ""
    posting_url = data.get("url") or ""
    for url in (apply_url, posting_url):
        hit = _matches_scam_list(apply_domain(url))
        if hit:
            return PredatoryVerdict(True, "scam_aggregator", f"domain_list_entry={hit}")

    # Rules 2 + 3 — link must be verified and domain-matched.
    if apply_url and data.get("link_status") != "verified":
        return PredatoryVerdict(
            True, "unverified_link", f"link_status={data.get('link_status', 'unverified')}"
        )
    if apply_url:
        domain = apply_domain(apply_url)
        company_domain = (data.get("company_domain") or "").lower().rstrip(".")
        if company_domain and not (
            domain == company_domain
            or domain.endswith("." + company_domain)
            or is_known_ats(domain)
        ):
            return PredatoryVerdict(
                True,
                "domain_mismatch",
                f"apply_domain={domain} company_domain={company_domain}",
            )

    return _ACCEPT


def enforce(
    records: list[Any],
    *,
    store_dir: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Screen a batch of postings; return ``(accepted, rejected)``.

    Every rejected posting is appended to the ingest store's append-only
    audit file with its ``reason_code`` and the original payload (§7.3).
    Accepted postings are returned as plain dicts, ready for
    :func:`engine.sources.ingest_store.upsert_many`.
    """
    from ..sources.ingest_store import append_rejected

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for record in records:
        data = record.to_dict() if hasattr(record, "to_dict") else dict(record)
        verdict = evaluate(data)
        if verdict.rejected:
            append_rejected(
                source=data.get("portal", data.get("source", "unknown")),
                external_id=data.get("external_id", ""),
                reason_code=verdict.reason_code,
                reason_detail=verdict.reason_detail,
                payload=data,
                store_dir=store_dir,
            )
            rejected.append({**data, "rejection_reason": verdict.reason_code})
            LOGGER.info(
                "predatory posting rejected",
                extra={"reason_code": verdict.reason_code, "detail": verdict.reason_detail},
            )
        else:
            accepted.append(data)
    return accepted, rejected
