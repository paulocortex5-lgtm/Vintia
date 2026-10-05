"""Security guardrails — PII redaction, prompt-injection guard, fraud filter.

Task 2.5 (anti-fraud guardrail) and 2.6 (injection + PII redactor) of the
master prompt v6.0. Every LLM call in the engine feeds on untrusted third-
party text (job descriptions, ATS resumes, portal listings) before it is
ever shown to a model; this package is the deterministic first line of
defence:

* :mod:`engine.security.redact` — scrub PII (email, phone, NINO, SSN, IBAN,
  card numbers, secrets) so it never reaches a prompt or an artifact.
* :mod:`engine.security.injection` — score and block prompt-injection
  attempts embedded in untrusted content (raises
  :class:`~engine.errors.InjectionDetectedError`).
* :mod:`engine.security.fraud` — score job listings for visa-mill /
  fee / middleman / guarantee signals (raises
  :class:`~engine.errors.FraudSignalError` when block-worthy).

All three are pure-Python, deterministic and fully testable with no
network or LLM dependency. They are deliberately *separate* from the LLM
stack so the guardrails hold even when every provider is unavailable.
"""

from __future__ import annotations

from .fraud import (
    FraudReport,
    FraudSignal,
    assess,
    block,
    screen,
)
from .injection import (
    InjectionFinding,
    InjectionReport,
    assess_injection,
    guard,
    normalize,
)
from .redact import (
    DEFAULT_KINDS,
    PII_KINDS,
    Redaction,
    RedactionResult,
    redact,
)

__all__ = [
    "DEFAULT_KINDS",
    "PII_KINDS",
    "FraudReport",
    "FraudSignal",
    "InjectionFinding",
    "InjectionReport",
    "Redaction",
    "RedactionResult",
    "assess",
    "assess_injection",
    "block",
    "guard",
    "normalize",
    "redact",
    "screen",
]
