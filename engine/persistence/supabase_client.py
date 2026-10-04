"""Supabase persistence (task 0.7).

Talks to the Supabase Postgres REST API over HTTP via ``httpx`` — no SDK
dependency at import time, so ``import engine`` stays clean even when
Supabase is not configured.

Per §0.1 STEP K, the Supabase copy is a write-through mirror and git on
the ``vantia-state`` branch is authoritative. Every method degrades to a
warning and ``False`` on failure instead of raising.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from typing import Any

import httpx

LOGGER = logging.getLogger("vantia.persistence.supabase")

REPLACE_ME = "REPLACE_ME"


class SupabaseClient:
    """Minimal Supabase REST client with graceful degradation."""

    def __init__(
        self,
        url: str | None = None,
        anon_key: str | None = None,
        service_role_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.anon_key = anon_key or os.environ.get("SUPABASE_ANON_KEY", "")
        self.service_role_key = service_role_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        """True only when real (non-placeholder) credentials are set."""
        return (
            self.url.startswith("http") and bool(self.anon_key) and REPLACE_ME not in self.anon_key
        )

    def _headers(self, service: bool = False) -> dict[str, str]:
        key = self.service_role_key if (service and self.service_role_key) else self.anon_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }

    def reachable(self) -> bool:
        """Probe ``GET /rest/v1/``; False when unconfigured or unreachable."""
        if not self.configured:
            return False
        try:
            resp = httpx.get(f"{self.url}/rest/v1/", headers=self._headers(), timeout=self.timeout)
        except httpx.HTTPError:
            return False
        return resp.status_code < 500

    def upsert(self, table: str, rows: list[dict[str, Any]], *, service: bool = False) -> bool:
        """Upsert ``rows`` into ``table``; never raises (STEP K)."""
        if not self.configured:
            LOGGER.warning(
                "supabase unconfigured; skipping upsert into %s (git remains authoritative)",
                table,
            )
            return False
        try:
            resp = httpx.post(
                f"{self.url}/rest/v1/{table}",
                json=rows,
                headers=self._headers(service),
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            LOGGER.warning(
                "supabase unreachable for %s: %s (git remains authoritative)", table, exc
            )
            return False
        if resp.status_code >= 400:
            LOGGER.warning(
                "supabase upsert %s failed: %s %s", table, resp.status_code, resp.text[:200]
            )
            return False
        return True

    def query(
        self,
        table: str,
        filters: dict[str, str],
        select: str = "*",
        *,
        service: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch matching rows via ``GET /rest/v1/<table>``; ``[]`` on failure.

        ``filters`` maps column -> "op.value" (e.g. ``{"event_id": "eq.x"}``).
        Used for webhook idempotency lookups (R50); RLS still applies on the
        server, so use ``service=True`` for engine-internal reads.
        """
        if not self.configured:
            return []
        params = urllib.parse.urlencode({**filters, "select": select})
        try:
            resp = httpx.get(
                f"{self.url}/rest/v1/{table}?{params}",
                headers=self._headers(service),
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            LOGGER.warning("supabase query %s failed: %s", table, exc)
            return []
        if resp.status_code >= 400:
            LOGGER.warning(
                "supabase query %s returned %s: %s",
                table,
                resp.status_code,
                resp.text[:200],
            )
            return []
        return list(resp.json())

    # ── Domain helpers ────────────────────────────────────────────
    def sync_state(self, state: dict[str, Any]) -> bool:
        """Write-through mirror of ``state.json`` (§0.1 STEP K)."""
        return self.upsert(
            "vantia_state",
            [
                {
                    "kind": "state",
                    "body": json.dumps(state),
                    "run_count": state.get("run_count"),
                    "updated_at": state.get("updated_at"),
                }
            ],
        )

    def log_artifact(self, artifact: dict[str, Any]) -> bool:
        """Record one artifact row (id, path, sha256, task_id)."""
        return self.upsert("artifact_metadata", [artifact])

    def log_llm_usage(self, usage: dict[str, Any]) -> bool:
        """Record one LLM provider-usage row."""
        return self.upsert("llm_usage", [usage])

    def log_cost(self, event: dict[str, Any]) -> bool:
        """Record one cost-ledger event."""
        return self.upsert("cost_ledger", [event])
