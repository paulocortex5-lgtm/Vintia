"""Vantia error taxonomy (§14).

Every error carries a stable machine-readable ``code`` used in logs, JSON
responses, the cost ledger, and GitHub issues opened for blocked tasks.
v4.0 adds :class:`InsufficientCredits` (R46) and :class:`StripeError`.
"""

from __future__ import annotations


class VantiaError(Exception):
    """Base class for every Vantia error."""

    code = "vantia_error"

    def __init__(self, message: str = "", *, code: str | None = None, **context: object) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.context = context

    def as_dict(self) -> dict[str, object]:
        return {"error": self.code, "message": self.message, "context": self.context}


class StateError(VantiaError):
    """state.json is missing, malformed, or otherwise unusable."""

    code = "state_error"


class StateLockBusy(StateError):
    """Another run holds the state lock and it is not stale (§0.1 STEP B)."""

    code = "state_lock_busy"


class TaskBlockedError(VantiaError):
    """Task failed 3 consecutive runs and is now blocked (§0.1 STEP G.5)."""

    code = "task_blocked"


class SchemaValidationError(VantiaError):
    """Artifact or state does not validate against its schema (§6)."""

    code = "schema_violation"

    def __init__(self, message: str = "", *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class FetchError(VantiaError):
    """A data source fetch failed (§8)."""

    code = "fetch_error"


class RateLimitError(FetchError):
    """Upstream rate limit hit (HTTP 429 or local rate limiter)."""

    code = "rate_limited"


class RobotsDisallowed(FetchError):
    """robots.txt forbids the URL (§8)."""

    code = "robots_disallowed"


class InjectionDetectedError(VantiaError):
    """Prompt-injection classifier flagged the input (§18)."""

    code = "prompt_injection_detected"


class FraudSignalError(VantiaError):
    """Anti-fraud guardrail matched (fee, middleman, unknown domain)."""

    code = "fraud_signal"


class LLMError(VantiaError):
    """Base class for all LLM provider failures (§17)."""

    code = "llm_error"


class LLMQuotaExceeded(LLMError):
    """Daily quota for a provider is exhausted (§17)."""

    code = "llm_quota_exceeded"


class LLMProviderFailure(LLMError):
    """Provider returned 5xx or timed out (§14)."""

    code = "llm_provider_failure"


class CircuitOpenError(VantiaError):
    """Circuit breaker is open; calls are short-circuited (§14)."""

    code = "circuit_open"


class InsufficientCredits(VantiaError):
    """v4.0 R46: credit balance is below the estimated cost of the task."""

    code = "insufficient_credits"

    def __init__(self, balance: int, required: int) -> None:
        super().__init__(
            f"insufficient credits: balance={balance} required={required}",
            balance=balance,
            required=required,
        )


class StripeError(VantiaError):
    """v4.0 §14: Stripe checkout / webhook failure."""

    code = "stripe_error"
