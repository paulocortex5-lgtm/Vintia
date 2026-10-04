"""Tests for ``engine/execute_step.py`` — task execution bookkeeping.

Covers the STEP G protocol: begin -> run -> validate artifacts -> chain ->
complete -> commit -> push, plus retry/block after 3 failures and the
idempotent re-run skip.
"""

from engine.execute_step import StepExecutor
from engine.hash_chain import HashChain
from engine.idempotency import IdempotencyRegistry
from engine.state_manager import VantiaState

COMMIT_SHA = "deadbeefcafebabe"


def _make(tmp_path):
    state = VantiaState(state_dir=str(tmp_path / ".vantia" / "state"))
    state.first_run()
    chain = HashChain(str(tmp_path / ".vantia" / "hash_chain.json"))
    registry = IdempotencyRegistry(str(tmp_path / ".vantia" / "idempotency_registry.json"))
    calls: list[str] = []

    def commit(message: str) -> str:
        calls.append(f"commit:{message}")
        return COMMIT_SHA

    def push() -> None:
        calls.append("push")

    executor = StepExecutor(state, chain, registry, commit=commit, push=push)
    return state, chain, registry, executor, calls


def _artifact(tmp_path) -> str:
    path = tmp_path / "artifact.json"
    path.write_text("{}", encoding="utf-8")
    return str(path)


def test_successful_task_completes_and_pushes(tmp_path):
    state, chain, registry, executor, calls = _make(tmp_path)
    result = executor.run("0.1", runner=lambda: [_artifact(tmp_path)], run_id=1)

    assert result.status == "complete"
    assert result.commit_sha == COMMIT_SHA
    assert not result.skipped
    task = state.load()["tasks"]["0.1"]
    assert task["status"] == "complete"
    assert task["commit_sha"] == COMMIT_SHA
    assert task["artifacts"]
    assert state.load()["last_completed_task"] == "0.1"
    assert registry.is_complete("0.1")
    assert chain.verify() == (True, 1)
    assert any(c.startswith("commit:vantia: begin 0.1") for c in calls)
    assert any(c.startswith("commit:vantia(0.1):") for c in calls)
    assert calls[-1] == "push"


def test_second_run_is_an_idempotent_skip(tmp_path):
    _state, chain, _registry, executor, calls = _make(tmp_path)
    executor.run("0.1", runner=lambda: [_artifact(tmp_path)], run_id=1)
    before = len(calls)
    result = executor.run("0.1", runner=lambda: [_artifact(tmp_path)], run_id=1)
    assert result.skipped is True
    assert result.status == "complete"
    assert len(calls) == before
    assert chain.length == 1


def test_retries_then_blocks_after_three_failures(tmp_path):
    state, chain, _registry, executor, calls = _make(tmp_path)

    def boom() -> None:
        raise RuntimeError("kaboom")

    assert executor.run("0.1", runner=boom, run_id=1).status == "retry"
    assert executor.run("0.1", runner=boom, run_id=2).status == "retry"
    third = executor.run("0.1", runner=boom, run_id=3)
    assert third.status == "blocked"
    assert "kaboom" in third.error

    data = state.load()
    task = data["tasks"]["0.1"]
    assert task["status"] == "blocked"
    assert task["attempts"] == 3
    assert data["consecutive_failures"]["0.1"] == 3
    assert "0.1" in data["blocked"]
    assert any("retry" in call for call in calls)
    assert any("blocked" in call for call in calls)
    # A failed task appends no chain record.
    assert chain.length == 0


def test_missing_artifact_counts_as_a_failure(tmp_path):
    state, chain, _registry, executor, _calls = _make(tmp_path)
    result = executor.run("0.1", runner=lambda: [str(tmp_path / "does-not-exist.json")], run_id=1)
    assert result.status == "retry"
    assert "missing artifact" in result.error
    assert state.load()["tasks"]["0.1"]["status"] == "in_progress"
    assert chain.length == 0


def test_runner_may_return_a_dict_of_artifacts(tmp_path):
    state, _chain, _registry, executor, _calls = _make(tmp_path)
    artifact = _artifact(tmp_path)
    result = executor.run("0.1", runner=lambda: {"artifacts": [artifact]}, run_id=1)
    assert result.status == "complete"
    assert state.load()["tasks"]["0.1"]["artifacts"] == [artifact]


def test_no_git_hooks_means_no_commits(tmp_path):
    state = VantiaState(state_dir=str(tmp_path / ".vantia" / "state"))
    state.first_run()
    chain = HashChain(str(tmp_path / ".vantia" / "chain.json"))
    executor = StepExecutor(state, chain)
    artifact = _artifact(tmp_path)
    result = executor.run("0.1", runner=lambda: [artifact], run_id=1)
    assert result.status == "complete"
    assert result.commit_sha is None
    assert state.load()["tasks"]["0.1"]["commit_sha"] is None
    assert chain.verify() == (True, 1)
