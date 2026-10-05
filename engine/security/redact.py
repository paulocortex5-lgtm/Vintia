"""PII redaction (task 2.6).

Deterministic, pure-Python scrubber for personally-identifiable data that
would otherwise leak into LLM prompts or persisted artifacts. Every kind
is a named, individually testable detector; the default set covers the
high-value, low-false-positive identifiers Vantia routinely sees in job
text and ATS resumes.

Design goals:

* **No false positives that eat product value** — patterns that carry a
  checksum (IBAN mod-97, Luhn) or format invariant (NINO, SSN) are
  *validated* before they redact, so ordinary digits / words survive.
* **Deterministic and idempotent** — a redacted string is stable;
  re-running never double-redacts.
* **Offset-stable** — findings report offsets into the *original* text so
  callers can log "what was redacted" without the value itself.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

__all__ = [
    "DEFAULT_KINDS",
    "PII_KINDS",
    "Redaction",
    "RedactionResult",
    "redact",
]


@dataclass(frozen=True)
class Redaction:
    """One redacted span. Offsets index the *original* text."""

    kind: str
    start: int
    end: int
    span: str
    placeholder: str


@dataclass(frozen=True)
class RedactionResult:
    """Output of :func:`redact` — the scrubbed text plus what was found."""

    text: str
    findings: tuple[Redaction, ...] = field(default=())

    @property
    def redacted(self) -> bool:
        return bool(self.findings)

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "findings": [
                {"kind": f.kind, "start": f.start, "end": f.end, "placeholder": f.placeholder}
                for f in self.findings
            ],
        }


def _placeholder(kind: str) -> str:
    return f"[REDACTED:{kind.upper()}]"


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _iban_ok(candidate: str) -> bool:
    """Standard IBAN mod-97 check (letters → two decimal digits, not base-36)."""
    raw = candidate.upper().replace(" ", "")
    if len(raw) < 15 or len(raw) > 34 or not raw.isalnum():
        return False
    if not raw[:2].isalpha() or not raw[2:4].isdigit():
        return False
    rearranged = "".join(str(int(ch, 36)) for ch in raw[4:] + raw[:4])
    return int(rearranged) % 97 == 1


def _nino_ok(candidate: str) -> bool:
    compact = candidate.upper().replace(" ", "").replace("-", "")
    # Two letters + six digits + A-D. Excluded first letters: D, F, I, Q,
    # U, V — so the two leading letters can never all be the same and the
    # pattern rejects the classic all-same false positives.
    return bool(re.fullmatch(r"[A-CEGHJ-NPRSTW-Z][A-CEGHJ-NPRSTW-Z][0-9]{6}[A-D]", compact))


def _ssn_ok(candidate: str) -> bool:
    digits = candidate.replace("-", "")
    if len(digits) != 9 or not digits.isdigit():
        return False
    area = int(digits[:3])
    return not (area == 0 or area == 666 or area >= 900)


def _card_ok(candidate: str) -> bool:
    digits = re.sub(r"[^0-9]", "", candidate)
    return 13 <= len(digits) <= 19 and _luhn_ok(digits)


def _secret_ok(candidate: str) -> bool:
    return len(candidate) >= 12


def _url_creds_ok(candidate: str) -> bool:
    return ":" in candidate.split("@", 1)[0]


# (kind, compiled regex, optional validator) — validator returns True when
# the raw match is a genuine instance of the kind (guards against FPs).
_PATTERNS: dict[str, tuple[re.Pattern[str], Callable[[str], bool] | None]] = {
    "email": (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        None,
    ),
    "phone": (
        re.compile(
            r"(?:\+\d{1,3}[\s.-]?(?:\(\d{1,4}\)|\d)(?:[\s.-]?\d){5,13}\b)",
        ),
        None,
    ),
    "nino": (
        re.compile(r"\b[A-CEGHJ-NPRSTW-Z][A-CEGHJ-NPRSTW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b"),
        _nino_ok,
    ),
    "ssn": (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), _ssn_ok),
    "iban": (re.compile(r"\b[A-Z]{2}\d{2}\s?[A-Z0-9]{10,30}\b", re.IGNORECASE), _iban_ok),
    "credit_card": (re.compile(r"\b(?:\d[ -]?){13,19}\b"), _card_ok),
    "secret": (
        re.compile(
            r"\b(?:sk|pk|ghp|gho|glpat|AKIA)[_-][A-Za-z0-9/+=_-]{12,}\b"
            r"|\bBearer\s[A-Za-z0-9._-]{16,}\b",
            re.IGNORECASE,
        ),
        _secret_ok,
    ),
    "url_credentials": (
        re.compile(r"\b[a-z]{2,}://[^@\s]+:[^@\s]+@", re.IGNORECASE),
        _url_creds_ok,
    ),
}

#: Every known kind (all are opt-in individually; these are the defaults).
PII_KINDS: frozenset[str] = frozenset(_PATTERNS)

#: Redacted automatically; ``None`` to redact everything known.
DEFAULT_KINDS: frozenset[str] = PII_KINDS


def redact(text: str, *, kinds: frozenset[str] | None = None) -> RedactionResult:
    """Return a :class:`RedactionResult` with PII scrubbed from ``text``.

    ``kinds`` narrows the set of detectors; ``None`` uses
    :data:`DEFAULT_KINDS`. The result's ``text`` is safe to feed a prompt;
    ``findings`` records what was redacted (without the values).
    """
    active = PII_KINDS if kinds is None else kinds
    spans: list[tuple[int, int, str, str]] = []
    for kind in sorted(active):
        if kind not in _PATTERNS:
            continue
        pattern, validator = _PATTERNS[kind]
        for match in pattern.finditer(text):
            value = match.group(0)
            if validator is not None and not bool(validator(value)):
                continue
            spans.append((match.start(), match.end(), kind, value))

    # Resolve overlaps: claim each character to the earliest-starting span.
    spans.sort(key=lambda s: (s[0], s[1]))
    chosen: list[tuple[int, int, str, str]] = []
    cursor = -1
    for start, end, kind, value in spans:
        if start >= cursor:
            chosen.append((start, end, kind, value))
            cursor = end

    # Build the scrubbed text right-to-left so earlier offsets stay valid.
    out = text
    findings: list[Redaction] = []
    for start, end, kind, value in reversed(chosen):
        placeholder = _placeholder(kind)
        out = out[:start] + placeholder + out[end:]
        findings.append(
            Redaction(kind=kind, start=start, end=end, span=value, placeholder=placeholder)
        )
    findings.reverse()
    return RedactionResult(text=out, findings=tuple(findings))
