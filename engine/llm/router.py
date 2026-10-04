"""LLM provider router — registry loading, key filtering, chain selection.

Deliverable of task 1.6 (master prompt v4.0).

Rules enforced here
  * R26 — every LLM call in the engine goes through this module
  * R27 — free-tier providers are exhausted in order before paid ones
  * R34 — credentials live in env vars named in providers.yaml
  * R36 — ``VANTIA_LLM_PROFILE`` selects the chain (default ``free_only``)
  * R38 — a new provider is a YAML entry, never a code change
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..errors import LLMProviderFailure
from . import quota as quota_module

DEFAULT_PROFILE = "free_only"
DEFAULT_REGISTRY_PATH = Path(__file__).with_name("providers.yaml")

DEFAULT_LIMITS: dict[str, float] = {"rpm": 10, "rpd": 100}


@dataclass(frozen=True)
class LLMModel:
    """One model entry from providers.yaml."""

    id: str
    max_tokens: int = 2048
    ctx: int = 32768
    in_usd_per_mtok: float = 0.0
    out_usd_per_mtok: float = 0.0

    @property
    def is_free(self) -> bool:
        return self.in_usd_per_mtok <= 0 and self.out_usd_per_mtok <= 0

    def usd_per_call(self, tokens_in: int, tokens_out: int) -> float:
        """Estimated cost of one call in USD."""
        return round(
            tokens_in / 1_000_000.0 * self.in_usd_per_mtok
            + tokens_out / 1_000_000.0 * self.out_usd_per_mtok,
            8,
        )


@dataclass(frozen=True)
class LLMProvider:
    """One provider entry from providers.yaml."""

    id: str
    display: str
    tier: str  # "free" | "paid"
    base_url: str
    api_key_env: str = ""
    auth_header: str | None = "Bearer {key}"
    api_key_header: str | None = None
    payload_style: str = "openai"
    extra_headers: dict[str, str] = field(default_factory=dict)
    url_vars: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)
    limits: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_LIMITS))
    models: list[LLMModel] = field(default_factory=list)

    # ── Convenience ───────────────────────────────────────────────────
    @property
    def is_free(self) -> bool:
        return self.tier == "free"

    @property
    def default_model(self) -> LLMModel:
        if not self.models:
            raise LLMProviderFailure(f"{self.id}: no models registered")
        return self.models[0]

    def get_model(self, model_id: str | None) -> LLMModel:
        """Resolve ``model_id`` against the registry; default = models[0]."""
        if model_id is None:
            return self.default_model
        for model in self.models:
            if model.id == model_id:
                return model
        known = ", ".join(m.id for m in self.models) or "(none)"
        raise LLMProviderFailure(f"{self.id}: unknown model {model_id!r}; known: {known}")

    # ── Availability ──────────────────────────────────────────────────
    def has_key(self, environ: dict[str, str] | None = None) -> bool:
        """True when the credential (and URL vars) are configured."""
        env = os.environ if environ is None else environ
        if self.api_key_env and not env.get(self.api_key_env):
            return False
        for value in self.url_vars.values():
            if value and not env.get(value):
                return False
        return True

    # ── Request construction ───────────────────────────────────────────
    def resolve_url(self, model: LLMModel, environ: dict[str, str] | None = None) -> str:
        """Expand ``{model}`` and ``url_vars`` placeholders in base_url."""
        env = os.environ if environ is None else environ
        url = self.base_url
        for placeholder, env_var in self.url_vars.items():
            value = model.id if env_var == "" else (env.get(env_var) or "")
            url = url.replace("{" + placeholder + "}", value)
        return url.replace("{model}", model.id)

    def build_headers(
        self, model: LLMModel, environ: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Authorization + provider-specific headers (R11 user-agent)."""
        env = os.environ if environ is None else environ
        headers = {"User-Agent": "Vantia/0.6 (+https://vantia.ai/bot)"}
        headers.update(self.extra_headers)
        key_value = env.get(self.api_key_env, "") if self.api_key_env else ""
        if self.api_key_header:
            headers[self.api_key_header] = key_value
        elif self.auth_header and key_value:
            headers["Authorization"] = self.auth_header.format(key=key_value)
        return headers

    def build_params(
        self, model: LLMModel, environ: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Extra URL query params (e.g. Gemini/Vertex ``key=``)."""
        env = os.environ if environ is None else environ
        params: dict[str, str] = {}
        for name, env_var in self.query_params.items():
            value = model.id if env_var == "" else (env.get(env_var) or "")
            if value:
                params[name] = value
        return params


def _model_from(raw: Any) -> LLMModel:
    if not isinstance(raw, dict):
        raise LLMProviderFailure(f"model entry must be a mapping, got {type(raw).__name__}")
    model_id = raw.get("id")
    if not isinstance(model_id, str) or not model_id:
        raise LLMProviderFailure("model entry requires a non-empty string 'id'")
    return LLMModel(
        id=model_id,
        max_tokens=int(raw.get("max_tokens", 2048)),
        ctx=int(raw.get("ctx", 32768)),
        in_usd_per_mtok=float(raw.get("in_usd_per_mtok", 0.0)),
        out_usd_per_mtok=float(raw.get("out_usd_per_mtok", 0.0)),
    )


def _provider_from(raw: Any) -> LLMProvider:
    if not isinstance(raw, dict):
        raise LLMProviderFailure(f"provider entry must be a mapping, got {type(raw).__name__}")
    provider_id = raw.get("id")
    if not isinstance(provider_id, str) or not provider_id:
        raise LLMProviderFailure("provider entry requires a non-empty string 'id'")
    models = [_model_from(m) for m in (raw.get("models") or [])]
    if not models:
        raise LLMProviderFailure(f"provider {provider_id} declares no models")
    tier = raw.get("tier", "free")
    if tier not in ("free", "paid"):
        raise LLMProviderFailure(f"provider {provider_id}: tier must be free|paid, got {tier!r}")
    style = raw.get("payload_style", "openai")
    if style not in ("openai", "gemini", "anthropic", "cohere"):
        raise LLMProviderFailure(f"provider {provider_id}: unknown payload_style {style!r}")
    if not raw.get("base_url"):
        raise LLMProviderFailure(f"provider {provider_id}: base_url is required")
    limits = dict(DEFAULT_LIMITS)
    for name in ("rpm", "rpd"):
        raw_limits = raw.get("limits") or {}
        if name in raw_limits:
            limits[name] = float(raw_limits[name])
    return LLMProvider(
        id=provider_id,
        display=str(raw.get("display", provider_id)),
        tier=tier,
        base_url=str(raw["base_url"]).strip(),
        api_key_env=str(raw.get("api_key_env") or ""),
        auth_header=raw.get("auth_header", "Bearer {key}"),
        api_key_header=raw.get("api_key_header"),
        payload_style=style,
        extra_headers={str(k): str(v) for k, v in (raw.get("extra_headers") or {}).items()},
        url_vars={str(k): str(v) for k, v in (raw.get("url_vars") or {}).items()},
        query_params={str(k): str(v) for k, v in (raw.get("query_params") or {}).items()},
        limits=limits,
        models=models,
    )


class LLMRegistry:
    """In-memory index over providers.yaml (order preserved = chain order)."""

    def __init__(
        self, providers: list[LLMProvider], profiles: dict[str, list[str]], path: Path
    ) -> None:
        self.providers = list(providers)
        self.profiles = dict(profiles)
        self.path = path
        seen: set[str] = set()
        for provider in self.providers:
            if provider.id in seen:
                raise LLMProviderFailure(f"duplicate provider id {provider.id!r}")
            seen.add(provider.id)

    # ── Lookups ───────────────────────────────────────────────────────
    def __len__(self) -> int:
        return len(self.providers)

    def __iter__(self):
        return iter(self.providers)

    def get(self, provider_id: str) -> LLMProvider:
        for provider in self.providers:
            if provider.id == provider_id:
                return provider
        known = ", ".join(p.id for p in self.providers) or "(none)"
        raise LLMProviderFailure(f"unknown provider {provider_id!r}; known: {known}")

    def free(self) -> list[LLMProvider]:
        return [p for p in self.providers if p.tier == "free"]

    def paid(self) -> list[LLMProvider]:
        return [p for p in self.providers if p.tier == "paid"]

    def stats(self) -> dict[str, int]:
        """Summary used by CLI ``vantia providers`` and /status."""
        return {
            "providers": len(self.providers),
            "free": len(self.free()),
            "paid": len(self.paid()),
            "models": sum(len(p.models) for p in self.providers),
        }


def load_registry(path: str | Path | None = None) -> LLMRegistry:
    """Parse providers.yaml into an :class:`LLMRegistry` (order preserved)."""
    registry_path = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    if not registry_path.is_file():
        raise LLMProviderFailure(f"provider registry not found: {registry_path}")
    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LLMProviderFailure(f"invalid providers.yaml: {exc}") from exc
    if not isinstance(raw, dict):
        raise LLMProviderFailure("providers.yaml must be a mapping")
    raw_providers = raw.get("providers")
    if not isinstance(raw_providers, list) or not raw_providers:
        raise LLMProviderFailure("providers.yaml must list at least one provider")
    providers = [_provider_from(p) for p in raw_providers]
    profiles = raw.get("profiles") or {}
    profiles = {
        str(k): [str(t) for t in (v if isinstance(v, list) else [v])] for k, v in profiles.items()
    }
    for profile_name, tiers in profiles.items():
        for tier in tiers:
            if tier not in ("free", "paid"):
                raise LLMProviderFailure(f"profile {profile_name!r}: unknown tier {tier!r}")
    if DEFAULT_PROFILE not in profiles:
        profiles[DEFAULT_PROFILE] = ["free"]
    return LLMRegistry(providers, profiles, registry_path)


def _default_quota() -> quota_module.QuotaTracker:
    return quota_module.default_tracker()


def _default_profile() -> str:
    return os.environ.get("VANTIA_LLM_PROFILE", DEFAULT_PROFILE)


def pick(
    profile: str | None = None,
    *,
    model: str | None = None,
    registry: LLMRegistry | None = None,
    environ: dict[str, str] | None = None,
    allow_paid: bool | None = None,
    quota_tracker: quota_module.QuotaTracker | None = None,
) -> list[LLMProvider]:
    """Ordered failover chain for the given profile (task 1.6 core API).

    Filtering rules, in order:
      1. profile tiers (``free_only`` | ``paid``); the chain keeps file
         order, which puts free providers before paid ones (R27)
      2. explicit ``model`` must exist on the provider (default models
         are always eligible)
      3. credential + URL vars present in the environment
      4. daily quota not exhausted (``quota_tracker``)

    Paid tiers only participate when ``allow_paid`` is True or
    ``VANTIA_ALLOW_PAID_LLM=1`` (R36/R40).
    """
    if registry is None:
        registry = load_registry()
    if profile is None:
        profile = _default_profile()
    tiers = registry.profiles.get(profile)
    if tiers is None:
        known = ", ".join(sorted(registry.profiles)) or "(none)"
        raise LLMProviderFailure(f"unknown profile {profile!r}; known: {known}")
    paid_allowed = (
        allow_paid if allow_paid is not None else os.environ.get("VANTIA_ALLOW_PAID_LLM") == "1"
    )
    env = dict(os.environ) if environ is None else environ
    tracker = quota_tracker if quota_tracker is not None else _default_quota()
    chain: list[LLMProvider] = []
    for provider in registry.providers:
        if provider.tier not in tiers:
            continue
        if provider.tier == "paid" and not paid_allowed:
            continue
        if model is not None and model not in {m.id for m in provider.models}:
            continue
        if not provider.has_key(env):
            continue
        if not tracker.check_quota(provider.id):
            continue
        chain.append(provider)
    return chain


_registry_cache: dict[Path, LLMRegistry] = {}


def registry_for(path: str | Path | None = None) -> LLMRegistry:
    """Cached registry per file path (m2m: registry + provider lists)."""
    key = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    if key not in _registry_cache:
        _registry_cache[key] = load_registry(key)
    return _registry_cache[key]


def providers_summary(
    profile: str | None = None, include: str = "available"
) -> list[dict[str, Any]]:
    """JSON-safe provider list for CLI ``vantia providers`` and /metrics.

    ``include``: "available" (key present) or "all".
    """
    reg = registry_for()
    out: list[dict[str, Any]] = []
    if profile is None:
        profile = _default_profile()
    tiers = reg.profiles.get(profile, ["free"])
    for provider in reg.providers:
        if provider.tier not in tiers:
            continue
        entry: dict[str, Any] = {
            "id": provider.id,
            "display": provider.display,
            "tier": provider.tier,
            "payload_style": provider.payload_style,
            "models": [m.id for m in provider.models],
            "default_model": provider.default_model.id,
            "limits": dict(provider.limits),
            "available": provider.has_key(),
        }
        if include == "all" or entry["available"]:
            out.append(entry)
    return out
