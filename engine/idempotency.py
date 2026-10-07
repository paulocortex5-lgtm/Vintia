"""Idempotency registry (§16).

Maps a canonical task key to the artifacts it produced so that a re-run
of identical input never redoes work — "never re-do completed work" (§0).

Registry contents live in ``.vantia/idempotency_registry.json`` and are
committed on the ``vantia-state`` branch (§29).

Task 4.2 hardens persistence: every entry carries an ``entry_hash``
(SHA-256 over its canonical JSON), so an entry edited after the fact is
detected by :meth:`IdempotencyRegistry.verify` instead of silently
re-opening completed work.
"""

from __future__ import annotations

import hashlib
import json

from .json_utils import atomic_write_json, load_json
from .logging_config import utc_now


def key(*parts: str) -> str:
    """Deterministic SHA-256 key over ``parts``.

    Task ids are the stable identity; extra inputs may be appended to
    distinguish runs over different data (e.g. resume content hash).
    """
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _entry_hash(entry: dict) -> str:
    payload = {k: v for k, v in entry.items() if k != "entry_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class IdempotencyRegistry:
    """Persistent task-id -> artifacts registry (with tamper evidence)."""

    def __init__(self, path: str = ".vantia/idempotency_registry.json") -> None:
        self.path = path

    def _read(self) -> dict:
        data = load_json(self.path)
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict) -> None:
        atomic_write_json(self.path, data)

    def lookup(self, task_id: str) -> dict | None:
        """Return the recorded entry for ``task_id``, or None."""
        return self._read().get(key(task_id))

    def is_complete(self, task_id: str) -> bool:
        """True when ``task_id`` already produced its artifacts."""
        return (self.lookup(task_id) or {}).get("status") == "complete"

    def record_complete(self, task_id: str, artifacts: list[str]) -> str:
        """Mark ``task_id`` complete with its artifact paths."""
        digest = key(task_id)
        entry = {
            "task_id": task_id,
            "status": "complete",
            "artifacts": list(artifacts),
            "at": utc_now(),
        }
        entry["entry_hash"] = _entry_hash(entry)
        data = self._read()
        data[digest] = entry
        self._write(data)
        return digest

    def entries(self) -> list[dict]:
        """All recorded entries, oldest first."""
        data = self._read()
        rows = [row for row in data.values() if isinstance(row, dict)]
        return sorted(rows, key=lambda row: str(row.get("at", "")))

    def verify(self) -> tuple[bool, list[str]]:
        """Recompute every ``entry_hash``; ``(ok, offending task ids)``.

        Entries written before hardening (no ``entry_hash``) are
        reported too — unverifiable is not the same as verified.
        """
        bad: list[str] = []
        for digest, entry in self._read().items():
            if not isinstance(entry, dict) or "entry_hash" not in entry:
                bad.append(str((entry or {}).get("task_id", digest)))
                continue
            if _entry_hash(entry) != entry["entry_hash"]:
                bad.append(str(entry.get("task_id", digest)))
        return not bad, bad

    def forget(self, task_id: str) -> bool:
        """Remove an entry (used by ``vantia reset``)."""
        data = self._read()
        existed = key(task_id) in data
        if existed:
            del data[key(task_id)]
            self._write(data)
        return existed
