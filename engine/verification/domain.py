"""Domain verification (task 4.1) — DNS A/CNAME checks for launch domains.

Resolves a domain's CNAME chain and A records and compares them to an
expectation (a hosting provider or an explicit suffix). Every network
call goes through an injectable ``resolver(name, rtype) -> list[str]``
so tests never touch DNS. When ``dnspython`` is missing the system
resolver still answers A records (CNAMEs then come back empty and the
report says so) — verification degrades loudly, never silently.
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from dataclasses import dataclass

from ..logging_config import utc_now

__all__ = [
    "PROVIDER_CNAME_TARGETS",
    "DomainReport",
    "verify_domain",
]

#: Documented CNAME targets for the free-tier hosts (Render docs, Vercel docs).
PROVIDER_CNAME_TARGETS: dict[str, tuple[str, ...]] = {
    "render": ("onrender.com",),
    "vercel": ("cname.vercel-dns.com",),
}

ResolverFn = Callable[[str, str], list[str]]

_MAX_CHAIN = 5


def _default_resolve(name: str, rtype: str) -> list[str]:
    """System DNS via dnspython when installed, else stdlib A-only."""
    try:
        from dns import resolver as _dns_resolver  # type: ignore[import-not-found]
    except ImportError:
        _dns_resolver = None  # type: ignore[assignment]
    if _dns_resolver is not None:
        try:
            answers = _dns_resolver.resolve(name, rtype)
        except Exception:  # noqa: BLE001 — NXDOMAIN/timeout/NoAnswer all mean "no records"
            return []
        if rtype == "CNAME":
            return [str(answer.target).rstrip(".").lower() for answer in answers]
        return [str(answer) for answer in answers]
    if rtype != "A":
        return []
    try:
        return sorted({str(info[4][0]) for info in socket.getaddrinfo(name, None)})
    except socket.gaierror:
        return []


@dataclass(frozen=True)
class DomainReport:
    """Outcome of one domain check."""

    domain: str
    status: str  # "ok" | "cname_mismatch" | "nxdomain"
    expectation: str | None
    cnames: tuple[str, ...]
    addresses: tuple[str, ...]
    matched: bool | None  # None when no expectation was configured
    note: str
    checked_at: str

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "status": self.status,
            "expectation": self.expectation,
            "cnames": list(self.cnames),
            "addresses": list(self.addresses),
            "matched": self.matched,
            "note": self.note,
            "checked_at": self.checked_at,
            "ok": self.ok,
        }


def _chain(domain: str, resolve: ResolverFn) -> list[str]:
    """Follow CNAMEs from ``domain`` (max 5 hops); targets lower-cased."""
    chain: list[str] = []
    current = domain
    for _ in range(_MAX_CHAIN):
        answers = resolve(current, "CNAME")
        if not answers:
            break
        target = answers[0].rstrip(".").lower()
        if target in chain:
            break  # loop guard
        chain.append(target)
        current = target
    return chain


def _matches(chain: list[str], wants: tuple[str, ...]) -> bool:
    for hop in chain:
        for raw in wants:
            want = raw.strip().lower().lstrip("*").lstrip(".")
            if hop == want or hop.endswith(("." + want, want)):
                return True
    return False


def verify_domain(
    domain: str,
    *,
    expect: str | None = None,
    resolver: ResolverFn | None = None,
) -> DomainReport:
    """Check ``domain``'s DNS against ``expect`` (provider name or suffix).

    ``expect`` accepts a provider key from :data:`PROVIDER_CNAME_TARGETS`
    (``"render"``, ``"vercel"``) or a literal suffix
    (``"cname.vercel-dns.com"``). Without an expectation the report only
    records what DNS answered (``matched=None``) — an observation, not a
    pass/fail claim.
    """
    resolve = resolver or _default_resolve
    chain = _chain(domain, resolve)
    leaf = chain[-1] if chain else domain
    addresses = resolve(leaf, "A") or (resolve(domain, "A") if not chain else [])
    resolves = bool(chain or addresses)

    expectation: str | None = None
    matched: bool | None = None
    if expect:
        key = expect.strip().lower()
        wants = PROVIDER_CNAME_TARGETS.get(key, (key,))
        expectation = key
        matched = _matches(chain, wants) if resolves else False

    if not resolves:
        return DomainReport(
            domain=domain,
            status="nxdomain",
            expectation=expectation,
            cnames=tuple(chain),
            addresses=tuple(addresses),
            matched=False if expect else None,
            note="no CNAME or A records found for this name",
            checked_at=utc_now(),
        )
    if expect and not matched:
        note = (
            "CNAME target does not match the expected provider"
            if chain
            else "no CNAME found where a provider CNAME was expected"
        )
        return DomainReport(
            domain=domain,
            status="cname_mismatch",
            expectation=expectation,
            cnames=tuple(chain),
            addresses=tuple(addresses),
            matched=False,
            note=note,
            checked_at=utc_now(),
        )
    note = (
        f"matches expected target '{expect}'"
        if expect
        else "no expectation configured; observations only"
    )
    return DomainReport(
        domain=domain,
        status="ok",
        expectation=expectation,
        cnames=tuple(chain),
        addresses=tuple(addresses),
        matched=True if expect else None,
        note=note,
        checked_at=utc_now(),
    )
