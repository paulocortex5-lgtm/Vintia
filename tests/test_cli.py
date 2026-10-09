"""Golden-file CLI tests (5.1/5.2).

Each scenario drives the real click commands through a `CliRunner` with
the CWD redirected into a `tmp_path`: state, chain and registry all live
under `.vantia/` in that CWD, so the suite is fully hermetic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from engine.cli import main
from engine.hash_chain import HashChain
from engine.idempotency import IdempotencyRegistry
from engine.state_manager import VantiaState

RUNNER_OK = f"{Path(__file__).parent / 'cli_runners.py'}:run_ok"
RUNNER_FAIL = f"{Path(__file__).parent / 'cli_runners.py'}:run_fail"


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


@pytest.fixture()
def cli() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def inited(cli: CliRunner) -> CliRunner:
    result = cli.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    return cli


def _chain_events() -> list[dict]:
    """All event_type values recorded on the cross-run chain."""
    return [r.get("event_type") for r in HashChain().records]


# ── init / status ────────────────────────────────────────────────


def test_init_creates_state(cli: CliRunner) -> None:
    result = cli.invoke(main, ["init"])
    assert result.exit_code == 0
    state = VantiaState()
    assert state.exists
    assert len(state.load()["tasks"]) == 88


def test_init_is_a_noop_without_force(cli: CliRunner) -> None:
    assert cli.invoke(main, ["init"]).exit_code == 0
    result = cli.invoke(main, ["init"])
    assert result.exit_code == 0
    assert "state already exists" in result.output
    assert cli.invoke(main, ["init", "--force"]).exit_code == 0


def test_status_after_init(inited: CliRunner) -> None:
    result = inited.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "next runnable  : 0.1" in result.output
    assert "registry       : ok=True bad=none" in result.output


def test_status_fails_without_init(cli: CliRunner) -> None:
    result = cli.invoke(main, ["status"])
    assert result.exit_code != 0


# ── apply ────────────────────────────────────────────────────────


def test_apply_completes_task_and_appends_chain(inited: CliRunner) -> None:
    result = inited.invoke(main, ["apply", "--execute", RUNNER_OK])
    assert result.exit_code == 0, result.output
    assert (Path.cwd() / "artifact_51.txt").exists()
    task = VantiaState().load()["tasks"]["0.1"]
    assert task["status"] == "complete"
    # attempts only counts failures — a clean success stays at 0
    assert task["attempts"] == 0
    events = _chain_events()
    assert events == ["task_in_progress", "task_complete", "run_finished"]
    assert HashChain().verify()[0]


def test_apply_reuses_explicit_run_id(inited: CliRunner) -> None:
    result = inited.invoke(main, ["apply", "--run-id", "77", "--execute", RUNNER_OK])
    assert result.exit_code == 0
    assert "reusing run #77" in result.output


def _block_01(cli: CliRunner) -> list[int]:
    """Three consecutive failed applies are what block a task (STEP G.5)."""
    return [cli.invoke(main, ["apply", "--execute", RUNNER_FAIL]).exit_code for _ in range(3)]


def test_apply_failure_retries_then_blocks(inited: CliRunner) -> None:
    codes = _block_01(inited)
    assert codes == [1, 1, 2]  # retry, retry, blocked
    state = VantiaState().load()
    task = state["tasks"]["0.1"]
    assert task["status"] == "blocked"
    assert task["attempts"] == 3
    assert state["consecutive_failures"]["0.1"] == 3
    events = _chain_events()
    assert events.count("task_failed") == 2
    assert "task_blocked" in events
    # incident draft must survive offline (4.4)
    assert list(Path(".vantia/issues").glob("*.md"))


def test_apply_skips_blocked_task(inited: CliRunner) -> None:
    _block_01(inited)
    result = inited.invoke(main, ["apply", "0.1", "--execute", RUNNER_OK])
    assert result.exit_code == 1
    assert "skipping blocked task 0.1" in result.output


def test_apply_bad_runner_exits_nonzero(inited: CliRunner) -> None:
    result = inited.invoke(main, ["apply", "--execute", "definitely_missing_mod.fn"])
    assert result.exit_code == 1
    assert "cannot import runner module" in result.output


def test_apply_script_path_runner(inited: CliRunner) -> None:
    """`script.py:attr` sidesteps site-packages namespace collisions."""
    result = inited.invoke(main, ["apply", "0.2", "--execute", RUNNER_OK])
    assert result.exit_code == 0, result.output
    assert VantiaState().load()["tasks"]["0.2"]["status"] == "complete"


def test_apply_missing_attr_is_clean_error(inited: CliRunner) -> None:
    result = inited.invoke(main, ["apply", "--execute", RUNNER_OK.rsplit(":", 1)[0] + ":nope"])
    assert result.exit_code == 1
    assert "not a callable" in result.output


def test_apply_refuses_already_complete_task(inited: CliRunner) -> None:
    assert inited.invoke(main, ["apply", "--execute", RUNNER_OK]).exit_code == 0
    result = inited.invoke(main, ["apply", "0.1", "--execute", RUNNER_OK])
    assert result.exit_code == 1
    assert "already complete" in result.output


def test_apply_force_runs_a_blocked_task(inited: CliRunner) -> None:
    """``--force`` is the escape hatch for clearing a false block."""
    _block_01(inited)
    result = inited.invoke(main, ["apply", "0.1", "--force", "--execute", RUNNER_OK])
    assert result.exit_code == 0, result.output
    state = VantiaState().load()
    assert state["tasks"]["0.1"]["status"] == "complete"
    assert "0.1" not in state["blocked"]


# ── resume ───────────────────────────────────────────────────────


def test_resume_recovers_crashed_task(inited: CliRunner) -> None:
    VantiaState().begin_task("0.4")
    result = inited.invoke(main, ["resume", "--execute", RUNNER_OK])
    assert result.exit_code == 0, result.output
    state = VantiaState().load()
    assert state["tasks"]["0.4"]["status"] == "complete"
    assert not state.get("in_progress_task")
    assert "run_resumed" in _chain_events()


def test_resume_with_nothing_in_progress_runs_next(inited: CliRunner) -> None:
    result = inited.invoke(main, ["resume", "--execute", RUNNER_OK])
    assert result.exit_code == 0
    assert "nothing in progress" in result.output
    assert VantiaState().load()["tasks"]["0.1"]["status"] == "complete"


# ── verify ───────────────────────────────────────────────────────


def test_verify_passes_on_clean_state(inited: CliRunner) -> None:
    inited.invoke(main, ["apply", "--execute", RUNNER_OK])
    result = inited.invoke(main, ["verify"])
    assert result.exit_code == 0
    assert "overall: ok" in result.output


def test_verify_detects_missing_artifact(inited: CliRunner) -> None:
    inited.invoke(main, ["apply", "--execute", RUNNER_OK])
    os.remove("artifact_51.txt")
    result = inited.invoke(main, ["verify", "--task", "0.1"])
    assert result.exit_code == 1
    assert "FAIL" in result.output


def test_verify_detects_tampered_chain(inited: CliRunner) -> None:
    inited.invoke(main, ["apply", "--execute", RUNNER_OK])
    chain_path = Path(".vantia/hash_chain.json")
    data = json.loads(chain_path.read_text())
    data["chain"][0]["payload"]["task_id"] = "EVIL"
    chain_path.write_text(json.dumps(data))
    result = inited.invoke(main, ["verify"])
    assert result.exit_code == 1
    assert "FAIL  hash_chain" in result.output


def test_verify_json_report(inited: CliRunner) -> None:
    inited.invoke(main, ["apply", "--execute", RUNNER_OK])
    result = inited.invoke(main, ["verify", "--json"])
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert {c["check"] for c in payload["checks"]} >= {
        "hash_chain",
        "chain_audit",
        "registry",
        "schemas",
        "artifacts",
    }


def test_verify_flags_broken_schema(inited: CliRunner, tmp_path: Path) -> None:
    """A deliberately malformed schema must be caught, not silently shipped."""
    import importlib

    engine_dir = Path(importlib.import_module("engine").__file__).parent
    target = engine_dir / "schemas" / "zz_intentionally_broken.json"
    target.write_text("{ not valid json", encoding="utf-8")
    try:
        result = inited.invoke(main, ["verify"])
    finally:
        target.unlink()
    assert result.exit_code == 1
    assert "FAIL  schemas" in result.output


# ── reset ────────────────────────────────────────────────────────


def test_reset_reseeds_state_and_wipes_registry(inited: CliRunner) -> None:
    inited.invoke(main, ["apply", "--execute", RUNNER_OK])
    IdempotencyRegistry().record_complete("0.1", ["artifact_51.txt"])
    assert Path(".vantia/idempotency_registry.json").exists()
    result = inited.invoke(main, ["reset", "--yes"])
    assert result.exit_code == 0
    state = VantiaState().load()
    assert len(state["tasks"]) == 88
    assert state["tasks"]["0.1"]["status"] == "pending"
    assert not Path(".vantia/idempotency_registry.json").exists()
    assert "state_reset" in _chain_events()


def test_reset_hard_starts_new_chain(inited: CliRunner) -> None:
    inited.invoke(main, ["apply", "--execute", RUNNER_OK])
    assert HashChain().length > 1
    result = inited.invoke(main, ["reset", "--hard", "--yes"])
    assert result.exit_code == 0
    chain = HashChain()
    assert chain.length == 1
    assert chain.records[0]["payload"] == {"event": "chain_genesis", "note": "hard reset"}
    assert state_is_seeded()


def test_reset_hard_keeps_issue_inbox(inited: CliRunner) -> None:
    """4.4: incident drafts are never lost by a reset."""
    _block_01(inited)
    drafts = list(Path(".vantia/issues").glob("*.md"))
    assert drafts
    assert inited.invoke(main, ["reset", "--hard", "--yes"]).exit_code == 0
    assert list(Path(".vantia/issues").glob("*.md")) == drafts


def state_is_seeded() -> bool:
    """State exists and carries the full 88-task seed."""
    state = VantiaState()
    return state.exists and len(state.load()["tasks"]) == 88
