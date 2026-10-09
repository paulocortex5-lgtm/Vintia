"""Runner callables for the ``vantia apply`` / ``resume`` CLI tests (5.1).

A runner is a zero-arg callable that returns either a dict with an
``artifacts`` key or a list of artifact paths. StepExecutor verifies that
every artifact exists on disk before marking the task complete.
"""

from __future__ import annotations

from pathlib import Path


def run_ok() -> dict:
    """Write one artifact and report it back."""
    artifact = Path("artifact_51.txt")
    artifact.write_text("produced by tests.cli_runners.run_ok\n", encoding="utf-8")
    return {"artifacts": [str(artifact)]}


def run_fail() -> dict:
    """Always raise — used to exercise the retry/blocked path."""
    raise RuntimeError("simulated task failure")
