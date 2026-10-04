"""File-based run lock (§0.1 STEP B, §16).

The lock serialises runs so two concurrent agents cannot both mutate
``state.json``. Semantics:

* lock absent      -> acquire
* lock < 30 min    -> another run is active; refuse (exit 0 upstream)
* lock >= 30 min   -> stale; steal it and log an incident

The lock file is plain JSON so it can be inspected during debugging.
"""

from __future__ import annotations

import json
import os
import time

DEFAULT_STALE_AFTER_SEC = 30 * 60


class StateLock:
    """Advisory lock held by at most one run at a time."""

    def __init__(self, path: str, stale_after_sec: int = DEFAULT_STALE_AFTER_SEC) -> None:
        self.path = path
        self.stale_after_sec = stale_after_sec
        self._held = False

    def _read_holder(self) -> dict | None:
        try:
            with open(self.path, encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _is_stale(self, holder: dict) -> bool:
        return (time.time() - float(holder.get("acquired_at", 0))) >= self.stale_after_sec

    def acquire(self, owner: str = "", run_id: str | None = None, *, steal: bool = False) -> bool:
        """Try to take the lock. Returns True on success.

        With ``steal=True`` a stale lock is removed before acquiring.
        """
        if self._held:
            return True
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        holder = self._read_holder()
        if holder is not None:
            if steal or self._is_stale(holder):
                try:
                    os.unlink(self.path)
                except FileNotFoundError:
                    pass
            else:
                return False
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            return False
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "pid": os.getpid(),
                        "owner": owner,
                        "run_id": run_id,
                        "acquired_at": time.time(),
                    },
                    fh,
                )
        except BaseException:
            os.unlink(self.path)
            raise
        self._held = True
        return True

    @property
    def is_held(self) -> bool:
        return self._held

    def release(self) -> None:
        """Drop the lock. Idempotent and safe to call on error paths."""
        self._held = False
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
