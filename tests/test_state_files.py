"""CLI + on-disk state tests: ``init`` / ``status`` and the master version file.

``VantiaState`` resolves ``.vantia/state`` relative to the CWD, so the CLI
tests are executed with the CWD pinned to a temp directory.
"""

from pathlib import Path

from click.testing import CliRunner

from engine.cli import main
from engine.state_manager import VantiaState


def _runner_in(tmp_path, monkeypatch) -> CliRunner:
    monkeypatch.chdir(tmp_path)
    return CliRunner()


def test_cli_init_materialises_state(tmp_path, monkeypatch):
    result = _runner_in(tmp_path, monkeypatch).invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert "state ready" in result.output
    assert "tasks: 88" in result.output

    state = VantiaState()
    assert state.exists
    assert len(state.load()["tasks"]) == 88


def test_cli_init_twice_is_noop_without_force(tmp_path, monkeypatch):
    runner = _runner_in(tmp_path, monkeypatch)
    assert runner.invoke(main, ["init"]).exit_code == 0
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    assert "state already exists" in result.output


def test_cli_status_surfaces_next_runnable_and_chain(tmp_path, monkeypatch):
    runner = _runner_in(tmp_path, monkeypatch)
    assert runner.invoke(main, ["init"]).exit_code == 0
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0, result.output
    assert "next runnable  : 0.1" in result.output
    assert "hash chain     : len=0 ok=True" in result.output


def test_cli_status_json_shape(tmp_path, monkeypatch):
    runner = _runner_in(tmp_path, monkeypatch)
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["status", "--json"])
    assert result.exit_code == 0
    import json

    body = json.loads(result.output)
    assert body["counts"]["pending"] == 88
    assert body["next"] == ["0.1"]
    assert body["chain_ok"] is True


def test_cli_status_without_state_is_an_error(tmp_path, monkeypatch):
    result = _runner_in(tmp_path, monkeypatch).invoke(main, ["status"])
    assert result.exit_code != 0
    assert "no state" in result.output


def test_cli_version_prints_engine_version(tmp_path, monkeypatch):
    result = _runner_in(tmp_path, monkeypatch).invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.4.0" in result.output


def test_master_version_file_written_by_init(tmp_path, monkeypatch):
    _runner_in(tmp_path, monkeypatch).invoke(main, ["init"])
    master = Path(".vantia/master_version")
    assert master.read_text(encoding="utf-8").strip() == "4.0"


def test_lock_not_left_held_after_init(tmp_path, monkeypatch):
    state_dir = tmp_path / ".vantia" / "state"
    _runner_in(tmp_path, monkeypatch).invoke(main, ["init"])
    assert (state_dir / "state.json").exists()
    assert not (state_dir / "state.lock").exists(), "init must not leave a held lock"


def test_pending_tasks_from_real_seed(tmp_path):
    state = VantiaState(state_dir=str(tmp_path / ".vantia" / "state"))
    state.first_run()
    assert state.pending_tasks() == ["0.1"]
    assert len(state.load()["tasks"]) == 88
