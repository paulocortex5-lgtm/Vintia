"""Anti-fraud guardrail for job listings (task 2.5).

Visa-mill / recruiter fraud is the single biggest harm category in
international job-seeking: an employer that (a) demands the *candidate*
pay a fee, (b) promises a "guaranteed visa" through a third party, or
(c) contacts from a disposable domain while the posting claims a real
employer is a scam. This module scores each :class:`JobListing` for those
signals **before** it is ever shown to a model or a user.

Deterministic and provider-free: a weighted phrase corpus over the
listing's text plus structural signals (domain risk, contact/posting
domain mismatch). Verdicts:

* ``clean``  — no signals
* ``review`` — some signal; show the user a warning, keep the job
* ``block``  — block-worthy (fee-to-candidate + another strong signal);
  :func:`block` raises :class:`~engine.errors.FraudSignalError`

Product rule (session 7): signals *tag and warn*, they never silently
drop a job — only :func:`block`'s verdict may raise, and callers decide
what to do with it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..errors import FraudSignalError
from ..sources.portals.base import JobListing

__all__ = [
    "RISKY_TLDS",
    "FraudReport",
    "FraudSignal",
    "assess",
    "block",
    "screen",
]

#: TLDs commonly used for disposable / scam mail domains.
RISKY_TLDS: frozenset[str] = frozenset(
    {
        ".zip",
        ".tk",
        ".xyz",
        ".top",
        ".club",
        ".gq",
        ".cf",
        ".ml",
        ".icu",
        ".buzz",
        ".loan",
        ".click",
        ".wtf",
        ".monster",
    }
)

#: score → verdict thresholds.
FRAUD_THRESHOLD_BLOCK = 4.0
FRAUD_THRESHOLD_REVIEW = 2.0

# (kind, compiled regex over lowercased listing text, weight).
_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    (
        "fee_to_candidate",
        re.compile(
            r"pay (a |an )?(interview|visa|application|processing|registration|document) fee"
            r"|(candidate|applicant|job ?seeker|you) (must|will|shall|has to) pay (a |an )?fee"
            r"|(fee|amount|deposit) (payable|to be paid|to pay) (by|from|toward|towards) (the )?(candidate|applicant|you)"
            r"|(deduct|deduction of) (the )?(fee|salary|amount|deduction) (from|out of)"
            r"|refundable (fee|deposit)"
            r"|salary (will be )?deducted"
        ),
        2.0,
    ),
    (
        "visa_mill",
        re.compile(
            r"guaranteed (visa|sponsorship|sponsor|job|position|placement)"
            r"|we (handle|process|arrange|obtain) (your|the) (visa|sponsorship|work permit)"
            r"|(third[- ]party|partner|affiliate|sister company|agency) (will |is |can )?(sponsor|guarantee|process|handle) (your|the|a)"
            r"|no (experience|qualifications?|references?)( )?(needed|required|necessary)"
            r"|we (guarantee|ensure) (you|your) (will )?(be |get |a |an )?(sponsor|visa|job|position|placement)"
        ),
        2.0,
    ),
    (
        "guarantee",
        re.compile(
            r"100% (placement|success|job|guarantee)"
            r"|confirmed (offer|sponsorship|visa)"
            r"|you are guaranteed (a |an |the )?(job|position|visa|sponsorship|offer)"
        ),
        1.5,
    ),
    (
        "payment_red_flag",
        re.compile(
            r"paid via (bank )?transfer (after|following) (the )?(interview|selection|hiring)"
            r"|commission[- ]only\b|commission[- ]based only\b"
        ),
        1.5,
    ),
    (
        "urgency_pressure",
        re.compile(
            r"respond within \d+ (hours?|hrs?|days?)"
            r"|limited (slots|positions|spots) (left|remaining)"
            r"|\bact now\b|last (chance|call)"
            r"|position (will )?(lapse|close) (soon|immediately|tomorrow)"
        ),
        1.0,
    ),
)

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _host(value: str) -> str:
    """Domain of a host or URL, lowercased."""
    host = urlsplit(value).hostname or ""
    if not host and "://" not in value and "." in value:
        host = value.split("/")[0]
    return host.lower()


def _contacts(listing: JobListing) -> tuple[list[str], list[str]]:
    """(posting hosts, contact email hosts)."""
    posting = [_host(listing.url)] if listing.url else []
    extras: list[str] = []
    for key in ("email", "contact_email", "contact"):
        value = listing.extra.get(key)
        if isinstance(value, str) and "@" in value:
            extras.append(value.split("@", 1)[1])
    found = _EMAIL.findall(listing.description or "")
    extras.extend(m.split("@", 1)[1].lower() for m in found)
    return posting, [h.lower() for h in set(extras)]


@dataclass(frozen=True)
class FraudSignal:
    kind: str
    detail: str
    weight: float
    matched: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "detail": self.detail,
            "weight": self.weight,
            "matched": self.matched,
        }


@dataclass
class FraudReport:
    listing_url: str
    score: float
    verdict: str  # "clean" | "review" | "block"
    signals: tuple[FraudSignal, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.verdict == "block"

    @property
    def has_signals(self) -> bool:
        return bool(self.signals)

    def to_dict(self) -> dict[str, object]:
        return {
            "url": self.listing_url,
            "score": round(self.score, 3),
            "verdict": self.verdict,
            "signals": [s.to_dict() for s in self.signals],
        }


def assess(listing: JobListing) -> FraudReport:
    """Score one listing. Never raises — callers inspect ``report.verdict``."""
    text = " ".join(
        (listing.title, listing.company, listing.location, listing.description or "")
    ).lower()
    signals: list[FraudSignal] = []

    for kind, pattern, weight in _PATTERNS:
        for match in pattern.finditer(text):
            signals.append(
                FraudSignal(
                    kind=kind,
                    detail=f"listing text matches '{kind}' signal",
                    weight=weight,
                    matched=match.group(0),
                )
            )

    posting, contacts = _contacts(listing)
    for contact in contacts:
        if any(contact.endswith(tld) for tld in RISKY_TLDS):
            signals.append(
                FraudSignal(
                    kind="risky_domain",
                    detail=f"contact domain '{contact}' uses a high-risk TLD",
                    weight=1.0,
                    matched=contact,
                )
            )
    for host in posting:
        for contact in contacts:
            if (
                host
                and contact
                and host != contact
                and not (contact.endswith(host) or host.endswith(contact))
            ):
                signals.append(
                    FraudSignal(
                        kind="domain_mismatch",
                        detail=f"contact '{contact}' differs from posting host '{host}'",
                        weight=0.5,
                        matched=contact,
                    )
                )

    score = round(sum(s.weight for s in signals), 3)
    if score >= FRAUD_THRESHOLD_BLOCK:
        verdict = "block"
    elif score >= FRAUD_THRESHOLD_REVIEW:
        verdict = "review"
    else:
        verdict = "clean"
    return FraudReport(
        listing_url=listing.url, score=score, verdict=verdict, signals=tuple(signals)
    )


def block(listing: JobListing) -> FraudReport:
    """Assess and raise :class:`FraudSignalError` when the verdict is block.

    Returns the report otherwise, so callers can attach signals to
    artifacts for the ``review`` verdict.
    """
    report = assess(listing)
    if report.blocked:
        raise FraudSignalError(
            f"fraud guardrail blocked {listing.url} (score={report.score})",
            signals=[s.to_dict() for s in report.signals],
            score=report.score,
            verdict=report.verdict,
            url=listing.url,
        )
    return report


def screen(listings: Iterable[JobListing]) -> Iterator[FraudReport]:
    """Assess a batch lazily."""
    for listing in listings:
        yield assess(listing)
