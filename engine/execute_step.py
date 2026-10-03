"""Task execution orchestration (§0.1 STEP G).

Drives the commit + lock + state bookkeeping around a single task::

    mark in_progress -> commit "vantia: begin <id> (run N)"
      -> run() -> validate artifacts
      -> mark complete -> commit "vantia(<id>): <name> (run N)" -> push
    on failure:
      -> increment attempts
      -> attempts >= 3 ? blocked : retry  -> commit -> push

``commit`` and ``push`` are injected callables so the orchestrator stays
decoupled from git (tests pass in no-ops).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from .errors import VantiaError
from .hash_chain import HashChain
from .idempotency import IdempotencyRegistry
from .state_manager import BLOCKED_AFTER_ATTEMPTS, VantiaState

LOGGER = logging.getLogger("vantia.execute_step")


@dataclass
class TaskResult:
    """Outcome of one :meth:`StepExecutor.run` invocation."""

    task_id: str
    status: str  # "complete" | "retry" | "blocked"
    commit_sha: str | None = None
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None
    skipped: bool = False


class StepExecutor:
    """Execute one task with full bookkeeping."""

    def __init__(
        self,
        state: VantiaState,
        hash_chain: HashChain,
        registry: IdempotencyRegistry | None = None,
        commit: Callable[[str], str | None] | None = None,
        push: Callable[[], None] | None = None,
        max_attempts: int = BLOCKED_AFTER_ATTEMPTS,
    ) -> None:
        self.state = state
        self.hash_chain = hash_chain
        self.registry = registry
        self._commit = commit
        self._push = push
        self.max_attempts = max_attempts

    def run(
        self,
        task_id: str,
        runner: Callable[[], Any],
        run_id: int,
        runner_kwargs: dict[str, Any] | None = None,
    ) -> TaskResult:
        """Run ``runner`` for ``task_id`` and update state/chain/commits."""
        task = self.state.task(task_id)
        name = task.get("name", task_id)

        if self.registry is not None and self.registry.is_complete(task_id):
            LOGGER.info("task %s already complete; skipping (idempotency)", task_id)
            return TaskResult(
                task_id=task_id,
                status="complete",
                artifacts=list(self.state.task(task_id).get("artifacts", [])),
                skipped=True,
            )

        self.state.begin_task(task_id, run_id=run_id)
        begin_sha = self.commit(f"vantia: begin {task_id} (run {run_id})")

        try:
            outcome = runner(**(runner_kwargs or {}))
            artifacts = (
                list(outcome.get("artifacts", []))
                if isinstance(outcome, dict)
                else list(outcome or [])
            )
            for artifact in artifacts:
                if not os.path.exists(artifact):
                    raise VantiaError(
                        f"missing artifact: {artifact}",
                        task_id=task_id,
                        artifact=artifact,
                    )
            self.hash_chain.append(
                {
                    "event": "task_complete",
                    "task_id": task_id,
                    "run": run_id,
                    "artifacts": artifacts,
                }
            )
            completed = self.state.complete_task(task_id, commit_sha=begin_sha, artifacts=artifacts)
            commit_sha = self.commit(f"vantia({task_id}): {name} (run {run_id})")
            self.push()
            if self.registry is not None:
                self.registry.record_complete(task_id, artifacts)
            return TaskResult(
                task_id=task_id,
                status=completed.get("status", "complete"),
                commit_sha=commit_sha,
                artifacts=artifacts,
            )
        except Exception as exc:  # noqa: BLE001 - bookkeeping boundary
            LOGGER.exception("task %s failed: %s", task_id, exc)
            task = self.state.fail_task(
                task_id,
                str(exc),
                commit_sha=begin_sha,
                max_attempts=self.max_attempts,
            )
            if task.get("status") == "blocked":
                status = "blocked"
            else:
                status = "retry"
            self.commit(f"vantia: {status} {task_id} (run {run_id})")
            self.push()
            return TaskResult(task_id=task_id, status=status, error=str(exc))

    # ── git hooks ───────────────────────────────────────────────────
    def commit(self, message: str) -> str | None:
        if self._commit is None:
            return None
        return self._commit(message)

    def push(self) -> None:
        if self._push is not None:
            self._push()
