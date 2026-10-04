"""State manager — the authoritative ``.vantia/state/state.json`` (§4).

Responsibilities (§0.1):

* STEP A — first run materialises the packaged seed; corruption resets it
* STEP B — all writes are guarded by :class:`~engine.locking.StateLock`
* STEP C — dependency resolution picks the next runnable task
* STEP D/E/F/I — run bookkeeping (run id, cost, tokens, history)
* STEP G — task lifecycle: ``pending`` -> ``in_progress`` -> ``complete``
           -> (``blocked`` after 3 consecutive failures)

The git copy on the ``vantia-state`` branch is authoritative; Supabase is
a write-through mirror only (§0.1 STEP K, §2).
"""

from __future__ import annotations

import copy
import os
from typing import Any

from .errors import StateError, TaskBlockedError
from .json_utils import atomic_write_json, load_json
from .locking import StateLock
from .logging_config import utc_now

BLOCKED_AFTER_ATTEMPTS = 3
DEFAULT_STATE_DIR = ".vantia/state"


def seed_path() -> str:
    """Absolute path to the packaged v4.0 seed."""
    return os.path.join(os.path.dirname(__file__), "seed", "state.json")


class VantiaState:
    """Load, mutate, and persist the run state."""

    def __init__(self, state_dir: str = DEFAULT_STATE_DIR) -> None:
        self.state_dir = state_dir
        self.path = os.path.join(state_dir, "state.json")
        self._lock_path = os.path.join(state_dir, "state.lock")
        self.master_version_path = os.path.join(os.path.dirname(state_dir), "master_version")
        self._data: dict[str, Any] | None = None

    # ── Locking (§0.1 STEP B) ──────────────────────────────────────────
    @property
    def lock_path(self) -> str:
        return self._lock_path

    def lock(self) -> StateLock:
        return StateLock(self._lock_path)

    # ── Seed / first run (§0.1 STEP A) ─────────────────────────────────
    @property
    def exists(self) -> bool:
        return os.path.exists(self.path)

    def first_run(self) -> dict[str, Any]:
        """Materialise the packaged seed (only when state.json is absent).

        Raises :class:`StateError` if the state file already exists — use
        :meth:`reset` to force a fresh state.
        """
        if self.exists:
            raise StateError(f"state already exists at {self.path}; use .reset()")
        return self.reset()

    def reset(self) -> dict[str, Any]:
        """STEP A fallback: drop state and start over from the seed."""
        data = load_json(seed_path())
        if data is None:
            raise StateError(f"packaged seed missing: {seed_path()}")
        data = copy.deepcopy(data)
        data["created_at"] = utc_now()
        data["updated_at"] = utc_now()
        data.setdefault("run_history", []).clear()
        atomic_write_json(self.path, data)
        self._write_master_version(str(data.get("master_prompt_version", "4.0")))
        self._data = data
        return data

    def _write_master_version(self, version: str) -> None:
        os.makedirs(os.path.dirname(self.master_version_path), exist_ok=True)
        with open(self.master_version_path, "w", encoding="utf-8") as fh:
            fh.write(f"{version}\n")

    # ── Load / save ────────────────────────────────────────────────────
    def load(self) -> dict[str, Any]:
        """Load state into memory (cached after the first call)."""
        if self._data is None:
            self._data = load_json(self.path)
            if self._data is None:
                raise StateError(f"state missing: {self.path}")
        return self._data

    def save(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Persist state atomically and refresh ``updated_at``."""
        payload = data if data is not None else self._data
        if payload is None:
            raise StateError("nothing to save: state has not been loaded")
        payload["updated_at"] = utc_now()
        atomic_write_json(self.path, payload)
        self._data = payload
        return payload

    def invalidate(self) -> None:
        """Drop the in-memory cache (call after an external writer)."""
        self._data = None

    # ── Tasks (§0.1 STEP C/G) ──────────────────────────────────────────
    def task(self, task_id: str) -> dict[str, Any]:
        """Return the raw task dict for ``task_id``."""
        tasks = self.load()["tasks"]
        if task_id not in tasks:
            raise StateError(f"unknown task: {task_id}")
        return tasks[task_id]

    def pending_tasks(self) -> list[str]:
        """Pending tasks whose dependencies are all complete (STEP C)."""
        data = self.load()
        tasks = data["tasks"]
        ready: list[str] = []
        for task_id, task in tasks.items():
            if task.get("status") != "pending":
                continue
            deps = task.get("depends_on") or []
            unsatisfied = [dep for dep in deps if tasks.get(dep, {}).get("status") != "complete"]
            if not unsatisfied:
                ready.append(task_id)
        ready.sort(key=lambda t: tuple(int(part) for part in t.split(".")))
        return ready

    def begin_task(self, task_id: str, run_id: int | None = None) -> dict[str, Any]:
        """Mark ``task_id`` in_progress (STEP G.1).

        ``attempts`` is only incremented by :meth:`fail_task`, so a task
        that succeeds on the first try records ``attempts: 1``.
        """
        data = self.load()
        task = self.task(task_id)
        if task.get("status") == "complete":
            raise TaskBlockedError(f"task {task_id} is already complete")
        task["status"] = "in_progress"
        if not task.get("started_at"):
            task["started_at"] = utc_now()
        data["in_progress_task"] = task_id
        if run_id is not None:
            data["run_count"] = max(int(data.get("run_count", 0)), int(run_id))
        return self.save(data)["tasks"][task_id]

    def complete_task(
        self,
        task_id: str,
        commit_sha: str | None = None,
        artifacts: list[str] | None = None,
    ) -> dict[str, Any]:
        """Mark ``task_id`` complete and record artifacts + commit (STEP G.3)."""
        data = self.load()
        task = self.task(task_id)
        task["status"] = "complete"
        task["completed_at"] = utc_now()
        if commit_sha:
            task["commit_sha"] = commit_sha
        if artifacts:
            merged = list(dict.fromkeys(list(task.get("artifacts") or []) + list(artifacts)))
            task["artifacts"] = merged
        data["last_completed_task"] = task_id
        data["in_progress_task"] = None
        data.setdefault("consecutive_failures", {}).pop(task_id, None)
        if task_id in data.get("blocked", []):
            data["blocked"].remove(task_id)
        return self.save(data)["tasks"][task_id]

    def fail_task(
        self,
        task_id: str,
        error: str,
        commit_sha: str | None = None,
        max_attempts: int = BLOCKED_AFTER_ATTEMPTS,
    ) -> dict[str, Any]:
        """Record a failure; block after ``max_attempts`` consecutive fails.

        STEP G.5: increment ``attempts``; if ``>= 3`` mark the task
        ``blocked`` (a GitHub issue should be opened by the caller) and
        log it as an incident. Otherwise keep ``in_progress`` so the next
        run retries it.
        """
        data = self.load()
        task = self.task(task_id)
        task["attempts"] = int(task.get("attempts", 0)) + 1
        if commit_sha:
            task["commit_sha"] = commit_sha
        task["last_error"] = error
        failures = data.setdefault("consecutive_failures", {})
        failures[task_id] = int(failures.get(task_id, 0)) + 1
        if failures[task_id] >= max_attempts:
            task["status"] = "blocked"
            if task_id not in data.setdefault("blocked", []):
                data["blocked"].append(task_id)
            data["in_progress_task"] = None
        else:
            task["status"] = "in_progress"
        return self.save(data)["tasks"][task_id]

    # ── Run bookkeeping (§0.1 STEP D/E/F/I) ───────────────────────────
    def start_run(self) -> int:
        """Bump ``run_count`` and append a fresh ``run_history`` entry."""
        data = self.load()
        data["run_count"] = int(data.get("run_count", 0)) + 1
        run_id = data["run_count"]
        entry = {"run": run_id, "started_at": utc_now(), "tasks": []}
        data.setdefault("run_history", []).append(entry)
        return self.save(data)["run_history"][-1]

    def end_run(
        self,
        run_id: int,
        *,
        usd: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        tasks: list[str] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        """Close ``run_history[run_id]`` and roll totals into cost_summary."""
        data = self.load()
        entry: dict[str, Any] = {"run": run_id}
        for recorded in reversed(data.get("run_history", [])):
            if recorded.get("run") == run_id:
                entry = recorded
                break
        entry["finished_at"] = utc_now()
        entry["usd"] = round(float(usd), 8)
        entry["tokens"] = {"in": int(tokens_in), "out": int(tokens_out)}
        if tasks:
            entry["tasks"] = list(tasks)
        if notes:
            entry["notes"] = notes
        summary = data.setdefault("cost_summary", {"total_usd": 0.0, "by_run": {}, "by_task": {}})
        summary["total_usd"] = round(float(summary.get("total_usd", 0.0)) + float(usd), 8)
        summary.setdefault("by_run", {})[str(run_id)] = round(float(usd), 8)
        self.save(data)
        return entry
