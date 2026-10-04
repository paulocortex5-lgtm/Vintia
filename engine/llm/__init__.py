"""Vantia LLM stack — provider registry, router, quota, client (tasks 1.5-1.7).

All LLM calls in the engine flow through :mod:`engine.llm.router`
(provider selection) and :mod:`engine.llm.client` (execution). Rules
R26 (router-only calls), R27 (free-before-paid ordering) and R38
(add provider = edit providers.yaml only) are enforced here.
"""

from __future__ import annotations

from ..errors import (
    AllProvidersExhausted,
    BudgetExceeded,
    LLMEmptyResponseError,
    LLMError,
    LLMNetworkError,
    LLMProviderFailure,
    LLMQuotaExceeded,
    LLMTimeoutError,
)
from .client import (
    DRY_RUN_STUB,
    LLMClient,
    LLMResult,
    build_envelope,
    build_payload,
    extract_result,
)
from .quota import QuotaTracker
from .router import (
    LLMModel,
    LLMProvider,
    LLMRegistry,
    load_registry,
    pick,
    providers_summary,
    registry_for,
)

__all__ = [
    "DRY_RUN_STUB",
    "AllProvidersExhausted",
    "BudgetExceeded",
    "LLMClient",
    "LLMEmptyResponseError",
    "LLMError",
    "LLMModel",
    "LLMNetworkError",
    "LLMProvider",
    "LLMProviderFailure",
    "LLMQuotaExceeded",
    "LLMRegistry",
    "LLMResult",
    "LLMTimeoutError",
    "QuotaTracker",
    "build_envelope",
    "build_payload",
    "extract_result",
    "load_registry",
    "pick",
    "providers_summary",
    "registry_for",
]
