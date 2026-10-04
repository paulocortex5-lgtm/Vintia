"""Per-provider daily quota tracking (task 1.6).

The router filters a failover chain by :func:`QuotaTracker.check_quota`;
the client reports successful calls via :meth:`QuotaTracker.increment_usage`
(R28 mirrors those to the Supabase ``llm_usage`` table). A local JSON cache
under ``.vantia/cache/llm/`` is the offline source of truth, so the engine
degrades gracefully when Supabase is unreachable (§0.7).

Limits come straight from ``providers.yaml``:
  * ``rpd`` — daily request cap; once the day's request count reaches it,
    the provider is skipped until the day rolls over
  * ``rpm`` — rolling one-minute cap (soft, to keep the free-tier chain fair)

``reset_daily_quotas`` implements the monthly/daily reset hook and is also
callable from a GitHub Actions cron.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import json_utils
from ..errors import LLMProviderFailure

if TYPE_CHECKING:
    from .router import LLMRegistry

# Same fallbacks as router.DEFAULT_LIMITS, redeclared here so that
# engine.llm.quota stays importable without importing engine.llm.router
# (which imports this module — a module-level cycle would be a SyntaxError).
DEFAULT_LIMITS: dict[str, float] = {"rpm": 10.0, "rpd": 100.0}
DEFAULT_CACHE_DIR = Path(".vantia/cache/llm")


def _today(now: str | None = None) -> str:
    """The quota day key (YYYY-MM-DD, UTC); injected for tests."""
    if now:
        return now[:10]
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _load_cache(path: Path, today: str) -> dict[str, Any]:
    data = json_utils.load_json(str(path))
    if not isinstance(data, dict):
        data = {}
    if data.get("date") != today:
        # Daily rollover: the previous day's counters no longer count.
        data = {}
    data.setdefault("date", today)
    data.setdefault("providers", {})
    return data


def _save_cache(path: Path, data: dict[str, Any]) -> None:
    json_utils.atomic_write_json(str(path), data)


def _entry_for(data: dict[str, Any], provider_id: str) -> dict[str, Any]:
    entry = data.setdefault("providers", {}).setdefault(provider_id, {})
    entry.setdefault("tokens_in", 0)
    entry.setdefault("tokens_out", 0)
    entry.setdefault("requests", 0)
    entry.setdefault("last_minute", 0)
    entry.setdefault("minute_ts", 0.0)
    return entry


class QuotaTracker:
    """Thread-safe local quota store with optional Supabase mirroring."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        now: str | None = None,
        registry: LLMRegistry | None = None,
        supabase_client: Any | None = None,
        limits: dict[str, float] | None = None,
    ) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self._path = self._cache_dir / "usage.json"
        self._now = now  # test injection; None = live UTC date
        self._limits = limits if limits is not None else dict(DEFAULT_LIMITS)
        self._registry = registry
        self._supabase = supabase_client
        # Re-entrant: usage_snapshot() holds the lock while calling
        # check_quota()/remaining_rpd(), which take it again (RLock keeps
        # that a no-op instead of deadlocking the process).
        self._lock = threading.RLock()

    # ── Injection points ──────────────────────────────────────────────
    def with_registry(self, registry: LLMRegistry) -> QuotaTracker:
        """Attach a registry so limits come from providers.yaml (m2m)."""
        self._registry = registry
        return self

    @property
    def supabase(self) -> Any:
        """Lazy Supabase client (created once, only if configured)."""
        if self._supabase is None:
            from ..persistence import SupabaseClient

            client = SupabaseClient()
            self._supabase = client if client.configured else False
        return self._supabase

    def set_supabase(self, client: Any | None) -> None:
        self._supabase = client

    # ── Limits ────────────────────────────────────────────────────────
    def limit(self, provider_id: str, kind: str) -> float:
        """rpm/rpd for a provider, from providers.yaml when attached."""
        if self._registry is not None:
            try:
                return float(self._registry.get(provider_id).limits.get(kind, DEFAULT_LIMITS[kind]))
            except LLMProviderFailure:
                pass
        return float(self._limits.get(kind, 0))

    # ── Quota API (task 1.6) ─────────────────────────────────────────
    def check_quota(self, provider_id: str) -> bool:
        """True when the provider still has daily/minute head-room."""
        with self._lock:
            data = _load_cache(self._path, _today(self._now))
            entry = _entry_for(data, provider_id)
            requests_today = int(entry.get("requests", 0))
            rpd = self.limit(provider_id, "rpd")
            if rpd > 0 and requests_today >= rpd:
                return False
            minute_cap = self.limit(provider_id, "rpm")
            if minute_cap > 0:
                last_minute = int(entry.get("last_minute", 0))
                if last_minute >= minute_cap:
                    return False
            return True

    def remaining_rpd(self, provider_id: str) -> int:
        """Requests left on the daily cap (-1 = unlimited)."""
        with self._lock:
            data = _load_cache(self._path, _today(self._now))
            entry = _entry_for(data, provider_id)
            rpd = self.limit(provider_id, "rpd")
            if rpd <= 0:
                return -1
            return max(0, int(rpd) - int(entry.get("requests", 0)))

    def increment_usage(
        self,
        provider_id: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        *,
        model: str | None = None,
        run_id: str | None = None,
        now_ts: float | None = None,
    ) -> dict[str, Any]:
        """Record one successful call; mirror to Supabase llm_usage (R28)."""
        import time as _time

        ts = now_ts if now_ts is not None else _time.time()
        with self._lock:
            data = _load_cache(self._path, _today(self._now))
            entry = _entry_for(data, provider_id)
            entry["tokens_in"] = int(entry.get("tokens_in", 0)) + int(tokens_in)
            entry["tokens_out"] = int(entry.get("tokens_out", 0)) + int(tokens_out)
            entry["requests"] = int(entry.get("requests", 0)) + 1
            # Rolling one-minute request window (soft rpm cap).
            if abs(ts - float(entry.get("minute_ts", ts))) >= 60.0:
                entry["minute_ts"] = ts
                entry["last_minute"] = 1
            else:
                entry["last_minute"] = int(entry.get("last_minute", 0)) + 1
            _save_cache(self._path, data)
        row = {
            "provider": provider_id,
            "model": model,
            "tokens_in": int(tokens_in),
            "tokens_out": int(tokens_out),
            "usage_date": _today(self._now),
            "run_id": run_id,
        }
        self._mirror_llm_usage(row)
        return row

    def _mirror_llm_usage(self, row: dict[str, Any]) -> None:
        client = self.supabase
        if not client:
            return
        try:
            client.log_llm_usage(row)
        except Exception:  # noqa: BLE001 — mirroring must never break a call
            import logging

            logging.getLogger("vantia.quota").warning(
                "llm_usage mirror failed; local cache is authoritative"
            )

    def reset_daily_quotas(self) -> int:
        """Clear the current day's local counters (cron / ``vantia reset``).

        Returns the number of provider entries cleared. The monthly credit
        reset lives in engine/credits — this only touches LLM quotas.
        """
        with self._lock:
            data = _load_cache(self._path, _today(self._now))
            cleared = len(data.get("providers") or {})
            data["providers"] = {}
            data["reset_at"] = datetime.now(UTC).isoformat()
            _save_cache(self._path, data)
        return cleared

    # ── Diagnostics ───────────────────────────────────────────────────
    def usage_snapshot(self) -> dict[str, Any]:
        """JSON-safe snapshot for ``vantia status`` and /metrics."""
        with self._lock:
            data = _load_cache(self._path, _today(self._now))
            snapshot: dict[str, Any] = {"date": data.get("date"), "providers": {}}
            for provider_id, entry in (data.get("providers") or {}).items():
                snapshot["providers"][provider_id] = {
                    "requests": int(entry.get("requests", 0)),
                    "tokens_in": int(entry.get("tokens_in", 0)),
                    "tokens_out": int(entry.get("tokens_out", 0)),
                    "remaining_rpd": self.remaining_rpd(provider_id),
                    "quota_ok": self.check_quota(provider_id),
                }
            return snapshot


_tracker: QuotaTracker | None = None


def default_tracker() -> QuotaTracker:
    """Process-wide tracker (used by :func:`router.pick`)."""
    global _tracker
    if _tracker is None:
        # Imported here: router.py imports this module at module level, so a
        # module-level router import in quota.py would be a circular import.
        from .router import load_registry

        _tracker = QuotaTracker().with_registry(load_registry())
    return _tracker


def reset_default_tracker() -> None:
    """Test hook: drop the singleton so a fresh cache dir is used."""
    global _tracker
    _tracker = None
