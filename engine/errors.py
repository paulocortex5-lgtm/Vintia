"""Vantia error taxonomy (§14).

Every error carries a stable machine-readable ``code`` used in logs, JSON
responses, the cost ledger, and GitHub issues opened for blocked tasks.
v4.0 adds :class:`InsufficientCredits` (R46). v6.0 replaces the legacy
payment error with :class:`PaddleError`.
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


class TransientFetchError(FetchError):
    """5xx or network failure while fetching — safe to retry with backoff (§8)."""

    code = "fetch_transient"


class RegisterPending(FetchError):
    """A sponsor register is legally mandated but not yet published (task 2.3).

    Example: Australia's public register of approved sponsors (Migration
    Amendment (Combatting Migrant Exploitation) Act 2026) must exist by
    2026-10-08; callers catch this and skip badging instead of failing.
    """

    code = "register_pending"


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


class LLMNetworkError(LLMError):
    """Connection/DNS failure talking to a provider (§14, retry 3x)."""

    code = "llm_network_error"


class LLMTimeoutError(LLMError):
    """Provider did not answer within the per-call timeout (R17)."""

    code = "llm_timeout"


class LLMEmptyResponseError(LLMError):
    """Provider returned a successful status with no usable content."""

    code = "llm_empty_response"


class AllProvidersExhausted(LLMError):
    """Every provider in the chain failed or is out of quota (R35)."""

    code = "all_providers_exhausted"

    def __init__(self, message: str = "", *, attempts: list[str] | None = None) -> None:
        super().__init__(message, attempts=attempts or [])
        self.attempts = attempts or []


class BudgetExceeded(VantiaError):
    """Run budget (VANTIA_MAX_COST_USD / R18) would be exceeded."""

    code = "budget_exceeded"

    def __init__(self, used_usd: float, budget_usd: float) -> None:
        super().__init__(
            f"budget exceeded: used=${used_usd:.4f} budget=${budget_usd:.4f}",
            used_usd=round(float(used_usd), 8),
            budget_usd=round(float(budget_usd), 8),
        )


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


class PaddleError(VantiaError):
    """v6.0 §14: Paddle checkout / webhook processing failure."""

    code = "paddle_error"


class AuthError(VantiaError):
    """Supabase Auth failure (task 8.1): missing/invalid/expired token."""

    code = "auth_error"


class WorkspaceError(VantiaError):
    """Workspace storage/service failure (tasks 8.2–8.4)."""

    code = "workspace_error"
