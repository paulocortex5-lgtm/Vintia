"""Tests for ``engine/incidents.py`` and its wiring into ``StepExecutor``
(task 4.4 — a blocked task must leave a GitHub issue or an offline draft).
"""

import json
import logging

from engine.execute_step import StepExecutor
from engine.hash_chain import HashChain
from engine.incidents import open_issue, slugify
from engine.state_manager import VantiaState

LOGGER = logging.getLogger(__name__)


def _state(tmp_path) -> VantiaState:
    state = VantiaState(state_dir=str(tmp_path / ".vantia" / "state"))
    state.first_run()
    return state


def test_slugify():
    assert slugify("Vantia: Task 4.4 — blocked?!") == "vantia-task-4-4-blocked"
    assert slugify("!!!") == "incident"


def test_open_issue_success_uses_gh(tmp_path):
    seen: list[list[str]] = []

    def runner(cmd: list[str]):
        seen.append(cmd)
        return 0, "https://github.com/example/vantia/issues/1"

    out = open_issue("title", "body", runner=runner, issues_dir=str(tmp_path / "issues"))
    assert out["method"] == "gh"
    assert out["detail"].startswith("https://")
    assert seen[0][:4] == ["gh", "issue", "create", "-t"]
    assert "-l" in seen[0]  # labels applied
    index = json.loads((tmp_path / "issues" / "index.json").read_text())
    assert index[0]["method"] == "gh"


def test_gh_failure_writes_an_offline_draft(tmp_path):
    out = open_issue(
        "Task 9.9 down",
        "body",
        runner=lambda cmd: (1, "HTTP 403 Forbidden"),
        issues_dir=str(tmp_path / "issues"),
    )
    assert out["method"] == "draft"
    assert out["path"].endswith(f"{slugify('Task 9.9 down')}.md")
    assert out["path"].startswith(str(tmp_path))
    index = json.loads((tmp_path / "issues" / "index.json").read_text())
    assert index[0]["method"] == "draft"


def test_a_broken_runner_still_gets_a_draft(tmp_path):
    def runner(cmd):
        raise OSError("gh exploded")

    out = open_issue("t", "b", runner=runner, issues_dir=str(tmp_path / "issues"))
    assert out["method"] == "draft"
    assert out["path"].endswith(".md")


def test_blocked_task_reports_an_incident(tmp_path):
    state = _state(tmp_path)
    chain = HashChain(str(tmp_path / ".vantia" / "hash_chain.json"))
    opened: list[tuple[str, str]] = []
    executor = StepExecutor(
        state,
        chain,
        None,
        commit=lambda m: "sha",
        push=lambda: None,
        issue_opener=lambda t, b: opened.append((t, b)) or {"method": "gh"},
    )

    def boom():
        raise RuntimeError("kaboom")

    assert executor.run("0.1", runner=boom, run_id=1).status == "retry"
    assert executor.run("0.1", runner=boom, run_id=2).status == "retry"
    result = executor.run("0.1", runner=boom, run_id=3)
    assert result.status == "blocked"

    assert len(opened) == 1
    title, body = opened[0]
    assert "0.1" in title and "run 3" in title
    assert "kaboom" in body
    assert state.load()["tasks"]["0.1"]["status"] == "blocked"


def test_default_opener_writes_a_draft_inside_the_state_tree(tmp_path):
    state = _state(tmp_path)
    chain = HashChain(str(tmp_path / ".vantia" / "hash_chain.json"))
    executor = StepExecutor(state, chain)

    def boom():
        raise RuntimeError("kaboom")

    for run_id in (1, 2, 3):
        executor.run("0.2", runner=boom, run_id=run_id)

    issues = tmp_path / ".vantia" / "issues"
    index = json.loads((issues / "index.json").read_text())
    assert index[0]["method"] == "draft"
    drafts = list(issues.glob("*.md"))
    assert len(drafts) == 1
    assert "kaboom" in drafts[0].read_text(encoding="utf-8")


def test_a_failing_opener_never_masks_the_block(tmp_path):
    state = _state(tmp_path)
    chain = HashChain(str(tmp_path / ".vantia" / "hash_chain.json"))
    executor = StepExecutor(
        state,
        chain,
        None,
        issue_opener=lambda t, b: 1 / 0,
    )

    def boom():
        raise RuntimeError("again")

    for run_id in (1, 2, 3):
        result = executor.run("0.3", runner=boom, run_id=run_id)
    assert result.status == "blocked"
    assert state.load()["tasks"]["0.3"]["status"] == "blocked"
