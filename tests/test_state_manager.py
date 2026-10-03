"""Tests for ``engine/state_manager.py`` — the authoritative state store.

Verifies: seed materialisation, dependency resolution, the task lifecycle
(in_progress -> complete / blocked after 3 attempts), failure-counter
reset, and run bookkeeping.
"""

from pathlib import Path

from engine.errors import StateError
from engine.state_manager import VantiaState


def _state(tmp_path) -> VantiaState:
    state = VantiaState(state_dir=str(tmp_path / ".vantia" / "state"))
    state.first_run()
    return state


def test_first_run_materialises_seed(tmp_path):
    state = VantiaState(state_dir=str(tmp_path / ".vantia" / "state"))
    assert not state.exists
    data = state.first_run()
    assert state.exists
    assert len(data["tasks"]) == 88
    assert data["run_count"] == 0
    assert data["in_progress_task"] is None
    master = Path(state.master_version_path)
    assert master.read_text(encoding="utf-8").strip() == "4.0"


def test_first_run_twice_raises(tmp_path):
    state = _state(tmp_path)
    try:
        state.first_run()
        assert False, "expected StateError on second first_run()"
    except StateError:
        pass


def test_reset_restores_seed(tmp_path):
    state = _state(tmp_path)
    state.begin_task("0.1")
    state.complete_task("0.1", commit_sha="abc123", artifacts=["engine/state_manager.py"])
    data = state.reset()
    assert data["tasks"]["0.1"]["status"] == "pending"
    assert data["last_completed_task"] is None
    assert data["run_count"] == 0
    assert state.load() == data


def test_pending_tasks_resolves_dependencies(tmp_path):
    state = _state(tmp_path)
    assert state.pending_tasks() == ["0.1"]
    state.complete_task("0.1", commit_sha="abc123")
    ready = state.pending_tasks()
    # 0.2 and 0.3 depend only on 0.1; 6.3 (Docker) also depends only on 0.1.
    assert set(ready) == {"0.2", "0.3", "6.3"}
    assert "0.1" not in ready


def test_begin_and_complete_task(tmp_path):
    state = _state(tmp_path)
    task = state.begin_task("0.1", run_id=1)
    assert task["status"] == "in_progress"
    assert task["started_at"] is not None
    data = state.load()
    assert data["in_progress_task"] == "0.1"
    assert data["run_count"] == 1

    task = state.complete_task("0.1", commit_sha="abc123", artifacts=["a.py", "b.py"])
    assert task["status"] == "complete"
    assert task["commit_sha"] == "abc123"
    assert task["completed_at"] is not None
    assert task["artifacts"] == ["a.py", "b.py"]
    data = state.load()
    assert data["last_completed_task"] == "0.1"
    assert data["in_progress_task"] is None


def test_artifacts_merge_without_duplicates(tmp_path):
    state = _state(tmp_path)
    state.complete_task("0.1", artifacts=["a.py"])
    state.complete_task("0.1", artifacts=["a.py", "b.py"])
    assert state.load()["tasks"]["0.1"]["artifacts"] == ["a.py", "b.py"]


def test_fail_blocks_after_three_attempts(tmp_path):
    state = _state(tmp_path)
    state.begin_task("0.1")
    task = state.fail_task("0.1", "boom")
    assert task["attempts"] == 1
    assert task["status"] == "in_progress"
    task = state.fail_task("0.1", "boom")
    assert task["attempts"] == 2
    assert task["status"] == "in_progress"
    task = state.fail_task("0.1", "boom")
    assert task["attempts"] == 3
    assert task["status"] == "blocked"
    data = state.load()
    assert "0.1" in data["blocked"]
    assert data["consecutive_failures"]["0.1"] == 3
    assert data["in_progress_task"] is None


def test_complete_clears_failure_counter(tmp_path):
    state = _state(tmp_path)
    state.begin_task("0.1")
    state.fail_task("0.1", "boom")
    state.fail_task("0.1", "boom")
    assert state.load()["consecutive_failures"]["0.1"] == 2
    state.complete_task("0.1", commit_sha="abc123")
    data = state.load()
    assert "0.1" not in data["consecutive_failures"]
    assert data["last_completed_task"] == "0.1"


def test_unknown_task_raises(tmp_path):
    state = _state(tmp_path)
    for call in (lambda: state.task("99.9"), lambda: state.begin_task("99.9")):
        try:
            call()
            assert False, "expected StateError for unknown task id"
        except StateError:
            pass


def test_run_bookkeeping(tmp_path):
    state = _state(tmp_path)
    entry = state.start_run()
    assert entry["run"] == 1
    assert entry["started_at"]
    record = state.end_run(1, usd=0.0042, tokens_in=100, tokens_out=50, tasks=["0.1"], notes="phase 0")
    assert record["run"] == 1
    assert record["usd"] == 0.0042
    assert record["tokens"] == {"in": 100, "out": 50}
    assert record["tasks"] == ["0.1"]
    assert record["finished_at"] is not None
    data = state.load()
    assert data["cost_summary"]["total_usd"] == 0.0042
    assert data["cost_summary"]["by_run"]["1"] == 0.0042


def test_end_run_accumulates_cost_summary(tmp_path):
    state = _state(tmp_path)
    state.start_run()
    state.end_run(1, usd=1.0)
    state.start_run()
    state.end_run(2, usd=0.5)
    summary = state.load()["cost_summary"]
    assert summary["total_usd"] == 1.5
    assert summary["by_run"] == {"1": 1.0, "2": 0.5}


def test_begin_task_rejects_completed(tmp_path):
    from engine.errors import TaskBlockedError

    state = _state(tmp_path)
    state.complete_task("0.1")
    try:
        state.begin_task("0.1")
        assert False, "expected TaskBlockedError"
    except TaskBlockedError:
        pass
