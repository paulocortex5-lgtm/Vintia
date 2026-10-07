"""Cross-run SHA-256 hash chain (§0, §4.3).

Every auditable event (task completion, state reset, sync) is appended to
a chain. Each record embeds the SHA-256 of its predecessor, so any
retroactive edit of history is detectable via :meth:`HashChain.verify`.

Chain records are committed on the ``vantia-state`` branch (§29).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .json_utils import atomic_write_json, load_json
from .logging_config import utc_now

GENESIS_HASH = "0" * 64


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(record: dict[str, Any]) -> bytes:
    """Canonical bytes for a record (no ``hash`` field)."""
    payload = {k: v for k, v in record.items() if k != "hash"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class HashChain:
    """Append-only, verifiable chain of run events."""

    def __init__(self, path: str = ".vantia/hash_chain.json") -> None:
        self.path = path
        self._records = self._load()

    def _load(self) -> list[dict]:
        data = load_json(self.path)
        if isinstance(data, dict):
            chain = data.get("chain")
            if isinstance(chain, list):
                return chain
        return []

    def _save(self) -> None:
        atomic_write_json(self.path, {"genesis": GENESIS_HASH, "chain": self._records})

    @property
    def records(self) -> list[dict]:
        return list(self._records)

    @property
    def length(self) -> int:
        return len(self._records)

    @property
    def tip(self) -> str:
        """Hash of the newest record, or the genesis hash when empty."""
        return self._records[-1]["hash"] if self._records else GENESIS_HASH

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        """Append ``event`` and persist the chain. Returns the new record."""
        record: dict[str, Any] = {
            "seq": len(self._records),
            "ts": utc_now(),
            "event_type": event.get("event", event.get("event_type", "event")),
            "payload": event,
            "prev_hash": self.tip,
        }
        record["hash"] = sha256_hex(_canonical(record))
        self._records.append(record)
        self._save()
        return record

    def verify(self) -> tuple[bool, int]:
        """Return ``(ok, index)``; ``index`` locates the first bad record.

        ``index`` equals the chain length when the whole chain is valid.
        """
        prev = GENESIS_HASH
        for i, record in enumerate(self._records):
            if record.get("prev_hash") != prev:
                return False, i
            if sha256_hex(_canonical(record)) != record.get("hash"):
                return False, i
            prev = record["hash"]
        return True, len(self._records)

    # ── task 4.3: cross-run audit surface ─────────────────────────────
    def audit(self) -> dict[str, Any]:
        """One-shot health report for the status page / run bookkeeping.

        ``first_bad_seq`` is ``None`` while the chain verifies; the
        moment any record (in *any* previous run) is edited, it names
        the first broken sequence number.
        """
        ok, index = self.verify()
        return {
            "ok": ok,
            "length": len(self._records),
            "tip": self.tip,
            "first_bad_seq": None if ok else index,
            "checked_at": utc_now(),
        }

    def record_run(
        self,
        run_id: int,
        *,
        tasks: list[str] | None = None,
        notes: str = "",
        usd: float = 0.0,
    ) -> dict[str, Any]:
        """Append a ``run_finished`` event — the cross-run audit trail.

        Every closed run (whoever closes it: ``StepExecutor`` or an
        operator running the state manager by hand) lands in the same
        append-only chain, so history stays verifiable across sessions.
        """
        return self.append(
            {
                "event": "run_finished",
                "run": run_id,
                "tasks": list(tasks or []),
                "notes": notes,
                "usd": usd,
            }
        )
