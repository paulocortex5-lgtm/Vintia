"""Cost ledger (§0.1 STEP F/J, §16).

Every LLM call is an auditable, cost-tracked event, appended to
``.vantia/costs.jsonl``. The engine enforces the run budget
(``VANTIA_MAX_COST_USD``) and emits a warning once usage passes 80%
of the cap. A zero/absent budget means "no hard cap" (local dev).
"""

from __future__ import annotations

import json
import os
import threading

from .logging_config import utc_now

DEFAULT_WARN_AT_PCT = 0.8


class CostTracker:
    """JSONL cost ledger with budget checks."""

    def __init__(
        self,
        path: str = ".vantia/costs.jsonl",
        *,
        max_usd: float = 0.0,
        warn_at_pct: float = DEFAULT_WARN_AT_PCT,
    ) -> None:
        self.path = path
        self.max_usd = float(max_usd)
        self.warn_at_pct = warn_at_pct
        self._lock = threading.Lock()

    # ── Events ────────────────────────────────────────────────────────
    def log_llm_call(
        self,
        *,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        usd: float = 0.0,
        task_id: str | None = None,
        run_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Append one LLM call event and return the stored record."""
        event = {
            "ts": utc_now(),
            "kind": "llm_call",
            "provider": provider,
            "model": model,
            "tokens_in": int(tokens_in),
            "tokens_out": int(tokens_out),
            "usd": round(float(usd), 8),
            "task_id": task_id,
            "run_id": run_id,
            "user_id": user_id,
        }
        with self._lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, default=str) + "\n")
        return event

    # ── Aggregates ─────────────────────────────────────────────────────
    def events(self, run_id: str | None = None):
        """Yield ledger events, optionally filtered by ``run_id``."""
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                if run_id is None or event.get("run_id") == run_id:
                    yield event

    def total_usd(self, run_id: str | None = None) -> float:
        return round(sum(e.get("usd", 0.0) for e in self.events(run_id)), 8)

    def tokens(self, run_id: str | None = None) -> tuple[int, int]:
        """Return ``(tokens_in, tokens_out)`` totals."""
        tokens_in = sum(e.get("tokens_in", 0) for e in self.events(run_id))
        tokens_out = sum(e.get("tokens_out", 0) for e in self.events(run_id))
        return tokens_in, tokens_out

    def budget_status(self, run_id: str | None = None) -> dict:
        """Budget summary used by §0.1 STEP E/J checks."""
        used = self.total_usd(run_id)
        budget = self.max_usd
        warn_at = round(budget * self.warn_at_pct, 6)
        return {
            "used_usd": used,
            "budget_usd": budget,
            "warn_threshold_usd": warn_at,
            "warning": budget > 0 and used >= warn_at,
            "exhausted": budget > 0 and used >= budget,
        }
