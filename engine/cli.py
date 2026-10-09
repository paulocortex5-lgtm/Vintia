"""Vantia CLI — the full ``init / apply / status / resume / verify /
reset`` surface (task 5.1).

* ``vantia init``    — materialise ``.vantia/state/state.json`` from the seed
* ``vantia apply``   — run one task through the StepExecutor harness with a
  caller-supplied runner (``--execute engine.module.attr``); blocked or
  already-complete tasks are skipped by default (``--force`` runs anyway)
* ``vantia status``  — task states, next runnable tasks, chain audit (4.3),
  registry integrity (4.2), optional 4.1 DNS check (``--verify-domain``)
* ``vantia resume``  — pick up the in-progress task after a crash; the
  recovery is appended to the cross-run hash chain as ``run_resumed``
* ``vantia verify``  — battery of integrity checks; exits non-zero on
  failure (``--json`` for machine-readable output)
* ``vantia reset``   — re-seed state, wipe the idempotency registry; the
  reset is recorded on the append-only chain (``--hard`` starts a new chain)

Console script ``vantia`` is declared in ``pyproject.toml``.
"""

from __future__ import annotations

import glob
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from . import __version__
from .execute_step import StepExecutor
from .hash_chain import HashChain
from .idempotency import IdempotencyRegistry
from .logging_config import utc_now
from .state_manager import VantiaState
from .verification.domain import verify_domain as check_domain


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="vantia")
def main() -> None:
    """Vantia — Universal Opportunity Engine."""


def _load_from_path(path: str) -> Any:
    """Import a standalone ``.py`` file by path, no package machinery."""
    spec = importlib.util.spec_from_file_location(
        "vantia_runner_" + str(abs(hash(os.path.abspath(path)))), path
    )
    if spec is None or spec.loader is None:
        raise click.ClickException(f"cannot build an import spec for {path!r}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_runner(path: str) -> Callable[[], Any]:
    """Resolve ``module.attr`` or ``path/to/script.py:attr`` to a callable.

    Dotted imports are retried once with the cwd prepended to
    ``sys.path`` so the CLI works in a repo that is not installed as a
    package. A ``:``-separated form loads the ``.py`` file directly from
    disk, which sidesteps namespace-package collisions entirely.
    """
    if ":" in path:
        module_path, _, attr = path.rpartition(":")
        if os.path.splitext(module_path)[1] != ".py":
            raise click.ClickException(f"--execute expects a .py path before ':' in {path!r}")
        module = _load_from_path(module_path)
    else:
        module_path, _, attr = path.rpartition(".")
        if not module_path:
            raise click.ClickException(f"--execute must be a dotted path, got: {path!r}")
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            raise click.ClickException(
                f"cannot import runner module {module_path!r}: {exc}"
            ) from exc
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError as exc:
                raise click.ClickException(
                    f"cannot import runner module {module_path!r}: {exc} — "
                    "use 'path/to/script.py:attr' to load a file straight from disk"
                ) from exc
    fn = getattr(module, attr, None)
    if fn is None or not callable(fn):
        raise click.ClickException(f"{path!r} is not a callable")
    return fn


def _git_commit(message: str) -> str | None:
    """Best-effort local ``git add -A && git commit``; None when not usable."""
    if shutil.which("git") is None:
        click.echo("warning: git not found; skipping commit", err=True)
        return None
    try:
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True, text=True)
        short = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return short or None
    except (subprocess.CalledProcessError, OSError) as exc:
        detail = (getattr(exc, "output", "") or str(exc)).strip()
        click.echo(f"warning: commit failed: {detail[:200]}", err=True)
        return None


def _pick_task(state: VantiaState, task: str | None) -> str:
    """Named task, else the in-progress task, else the next runnable one."""
    if task:
        return task
    in_progress = state.load().get("in_progress_task")
    if in_progress:
        return str(in_progress)
    pending = state.pending_tasks()
    if not pending:
        raise click.ClickException("no pending tasks remain — nothing to apply")
    return pending[0]


def _run_task(
    state: VantiaState,
    task_id: str,
    runner: Callable[[], Any],
    run_id: int | None,
    commit_fn: Callable[[str], str | None] | None,
) -> None:
    """Shared apply/resume core: StepExecutor bookkeeping + run closeout."""
    if run_id is None:
        # start_run returns the run_history entry; the id is its "run" key
        started = int(state.start_run()["run"])
        click.echo(f"run #{started}")
    else:
        started = int(run_id)
        click.echo(f"reusing run #{started}")
    chain = HashChain()
    registry = IdempotencyRegistry()
    executor = StepExecutor(
        state=state,
        hash_chain=chain,
        registry=registry,
        commit=commit_fn,
        push=None,
    )
    if not registry.is_complete(task_id):
        # Operator-level lifecycle on the cross-run chain (4.3): a crashed
        # run leaves task_in_progress with no matching task_complete — which
        # is exactly the gap `resume` closes.
        chain.append({"event": "task_in_progress", "task_id": task_id, "run": started})
    result = executor.run(task_id, runner, run_id=started)
    if result.status in ("complete", "skipped"):
        verb = "skipped (idempotent)" if result.skipped else "complete"
        click.echo(f"task {task_id} {verb}")
        click.echo(f"artifacts     : {', '.join(result.artifacts) or 'none recorded'}")
        if result.commit_sha:
            click.echo(f"commit        : {result.commit_sha}")
        state.end_run(started, tasks=[task_id], notes=result.status)
        chain.record_run(started, tasks=[task_id], notes=result.status)
        return
    chain.append(
        {
            "event": "task_blocked" if result.status == "blocked" else "task_failed",
            "task_id": task_id,
            "run": started,
            "error": result.error,
        }
    )
    click.echo(f"task {task_id} {result.status}: {result.error}", err=True)
    state.end_run(started, tasks=[task_id], notes=f"{result.status}: {result.error}")
    chain.record_run(started, tasks=[task_id], notes=f"{result.status}: {result.error}")
    raise SystemExit(1 if result.status == "retry" else 2)


@main.command("apply")
@click.argument("task", required=False, default=None)
@click.option(
    "--execute", "execute_path", required=True, help="Runner as 'module.attr' or 'script.py:attr'."
)
@click.option("--run-id", type=int, default=None, help="Reuse an existing run id.")
@click.option("--commit", "commit_flag", is_flag=True, help="git-commit the tree after success.")
@click.option("--force", is_flag=True, help="Run a blocked/already-complete task anyway.")
def apply_task(
    task: str | None, execute_path: str, run_id: int | None, commit_flag: bool, force: bool
) -> None:
    """Run one task through the StepExecutor harness.

    Executes ``runner = import(EXECUTE_PATH)()`` with full bookkeeping
    (state lifecycle, hash chain, idempotency registry, incident
    reporting). The runner returns either a dict with an ``artifacts``
    key or a list of artifact paths — StepExecutor verifies each
    artifact exists on disk before marking the task complete.

    A blocked or already-complete task is refused by default (exit 1);
    pass ``--force`` to run it anyway, which is how a recovered runner
    can clear a false block.
    """
    state = VantiaState()
    if not state.exists:
        raise click.ClickException(f"no state at {state.path}; run `vantia init` first")
    task_id = _pick_task(state, task)
    if task is None:
        click.echo(f"auto-picked task: {task_id}")
    data = state.load()
    already_done = IdempotencyRegistry().is_complete(task_id)
    if task_id in data.get("blocked", []) or already_done:
        reason = "blocked" if task_id in data.get("blocked", []) else "already complete"
        if not force:
            click.echo(f"skipping {reason} task {task_id}", err=True)
            raise click.ClickException(f"task {task_id} is {reason} (use --force to run anyway)")
    runner = _resolve_runner(execute_path)
    _run_task(state, task_id, runner, run_id, _git_commit if commit_flag else None)


@main.command("resume")
@click.option(
    "--execute", "execute_path", required=True, help="Runner as 'module.attr' or 'script.py:attr'."
)
@click.option("--run-id", type=int, default=None, help="Reuse an existing run id.")
def resume(execute_path: str, run_id: int | None) -> None:
    """Pick up the in-progress task after a crash.

    A crashed run leaves ``in_progress_task`` set in the state. ``resume``
    re-runs that task — and appends a ``run_resumed`` record to the
    cross-run hash chain, so the recovery is auditable rather than silent
    (the chain then shows an in_progress with no matching task_complete).
    """
    state = VantiaState()
    if not state.exists:
        raise click.ClickException(f"no state at {state.path}; run `vantia init` first")
    task_id = _pick_task(state, None)
    if state.load().get("in_progress_task"):
        HashChain().append({"event": "run_resumed", "task_id": task_id, "reason": "crash_recovery"})
        click.echo(f"resuming crashed task {task_id} (recorded on chain)")
    else:
        click.echo(f"nothing in progress; running next runnable task {task_id}")
    runner = _resolve_runner(execute_path)
    _run_task(state, task_id, runner, run_id, None)


@main.command()
@click.option("--force", is_flag=True, help="Reset an existing state file.")
def init(force: bool) -> None:
    """Create ``.vantia/state/state.json`` from the packaged seed."""
    state = VantiaState()
    if state.exists and not force:
        click.echo(f"state already exists: {state.path} (use --force to reset)")
        return
    data = state.reset()
    click.echo(f"state ready at {state.path}")
    click.echo(f"master prompt version: {data.get('master_prompt_version')}")
    click.echo(f"tasks: {len(data.get('tasks', {}))}")


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
@click.option(
    "--verify-domain", "verify_domain_flag", is_flag=True, help="Also run the task 4.1 DNS check."
)
@click.option("--domain", default=None, help="Domain to check (defaults to state 'domain').")
@click.option(
    "--expect", "expected", default=None, help="Expected CNAME provider/suffix, e.g. 'render'."
)
def status(
    as_json: bool, verify_domain_flag: bool, domain: str | None, expected: str | None
) -> None:
    """Summarise run state, next runnable tasks, chain + registry integrity."""
    state = VantiaState()
    if not state.exists:
        raise click.ClickException(f"no state at {state.path}; run `vantia init` first")
    data = state.load()
    counts: dict[str, int] = {}
    for task in data.get("tasks", {}).values():
        status_name = task.get("status", "pending")
        counts[status_name] = counts.get(status_name, 0) + 1
    chain = HashChain()
    registry_ok, registry_bad = IdempotencyRegistry().verify()
    summary = {
        "run_count": data.get("run_count"),
        "in_progress_task": data.get("in_progress_task"),
        "last_completed_task": data.get("last_completed_task"),
        "counts": counts,
        "next": state.pending_tasks()[:5],
        "blocked": data.get("blocked", []),
        "chain_length": chain.length,
        "chain_ok": chain.verify()[0],
        "chain_audit": chain.audit(),
        "registry_ok": registry_ok,
        "registry_bad": registry_bad,
    }
    if verify_domain_flag:
        target = domain or str(data.get("domain") or "")
        if not target:
            raise click.ClickException(
                "--verify-domain needs a domain: pass --domain or set 'domain' in the state"
            )
        summary["domain"] = check_domain(target, expect=expected).to_dict()
    if as_json:
        click.echo(json.dumps(summary, indent=2, sort_keys=True))
        return
    click.echo(f"run #{summary['run_count']}  counts={summary['counts']}")
    click.echo(f"last completed : {summary['last_completed_task']}")
    click.echo(f"next runnable  : {', '.join(summary['next'])}")
    click.echo(f"blocked        : {summary['blocked'] or 'none'}")
    audit = summary["chain_audit"]
    click.echo(
        f"hash chain     : len={summary['chain_length']} ok={summary['chain_ok']}"
        f" first_bad={audit['first_bad_seq']}"
    )
    click.echo(f"registry       : ok={registry_ok} bad={registry_bad or 'none'}")
    if "domain" in summary:
        report = summary["domain"]
        click.echo(
            f"domain         : {report['domain']} status={report['status']} — {report['note']}"
        )


@main.command("verify")
@click.option(
    "--task", "task_ids", default=None, help="Comma-separated tasks whose artifacts are checked."
)
@click.option("--domain", default=None, help="Also run the task 4.1 DNS check for this domain.")
@click.option("--expect", "expected", default=None, help="Expected CNAME provider/suffix.")
@click.option("--json", "as_json", is_flag=True, help="Emit a machine-readable report.")
def verify(task_ids: str | None, domain: str | None, expected: str | None, as_json: bool) -> None:
    """Run the integrity battery; exit non-zero when any check fails.

    Checks: hash-chain audit (4.3), registry integrity (4.2), JSON
    validity of every ``engine/schemas/*.json``, existence of every
    artifact recorded for ``--task`` tasks, and (with ``--domain``) the
    4.1 DNS check. Safe to run after every run and in CI.
    """
    state = VantiaState()
    if not state.exists:
        raise click.ClickException(f"no state at {state.path}; run `vantia init` first")
    chain = HashChain()
    checks: list[dict[str, Any]] = [
        {"check": "hash_chain", "ok": chain.verify()[0], "detail": f"length={chain.length}"},
    ]
    audit = chain.audit()
    checks.append(
        {
            "check": "chain_audit",
            "ok": bool(audit["ok"]),
            "detail": f"first_bad_seq={audit['first_bad_seq']} (expected none)",
        }
    )
    registry_ok, registry_bad = IdempotencyRegistry().verify()
    checks.append(
        {"check": "registry", "ok": registry_ok, "detail": f"bad={registry_bad or 'none'}"}
    )
    schema_dir = os.path.join(os.path.dirname(__file__), "schemas")
    bad_schemas: list[str] = []
    for path in sorted(glob.glob(os.path.join(schema_dir, "*.json"))):
        try:
            json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            bad_schemas.append(f"{os.path.basename(path)}: {exc}")
    checks.append(
        {
            "check": "schemas",
            "ok": not bad_schemas,
            "detail": f"{len(glob.glob(os.path.join(schema_dir, '*.json')))} files, invalid={bad_schemas or 'none'}",
        }
    )
    wanted = [t.strip() for t in (task_ids or "").split(",") if t.strip()]
    data = state.load()
    missing_artifacts: dict[str, list[str]] = {}
    for task_id in wanted:
        task = data.get("tasks", {}).get(task_id)
        if task is None:
            missing_artifacts[task_id] = ["task not in state"]
            continue
        absent = [a for a in task.get("artifacts", []) if not os.path.exists(a)]
        if absent:
            missing_artifacts[task_id] = absent
    checks.append(
        {
            "check": "artifacts",
            "ok": not missing_artifacts,
            "detail": f"tasks={wanted or 'none checked'} missing={missing_artifacts or 'none'}",
        }
    )
    if domain:
        report = check_domain(domain, expect=expected).to_dict()
        checks.append(
            {
                "check": "domain",
                "ok": report["status"] == "ok",
                "detail": f"{report['domain']} status={report['status']}",
            }
        )
    ok = all(c["ok"] for c in checks)
    if as_json:
        click.echo(json.dumps({"ok": ok, "checks": checks}, indent=2, sort_keys=True))
        return
    for check in checks:
        click.echo(f"{'PASS' if check['ok'] else 'FAIL'}  {check['check']:<14} {check['detail']}")
    click.echo(f"overall: {'ok' if ok else 'FAILED'}")
    if not ok:
        raise SystemExit(1)


@main.command("reset")
@click.option("--yes", "assume_yes", is_flag=True, help="Do not prompt for confirmation.")
@click.option("--hard", is_flag=True, help="Also start a brand-new hash chain.")
def reset_state(assume_yes: bool, hard: bool) -> None:
    """Re-seed state from the packaged seed.

    Wipes the idempotency registry (a fresh state must not inherit
    "already complete" claims from a previous lifecycle) and records the
    reset on the append-only hash chain so the wipe is tamper-evident.
    ``--hard`` starts a brand-new chain instead.
    """
    state = VantiaState()
    if not assume_yes:
        click.confirm(f"Reset state at {state.path}?", abort=True)
    chain = HashChain()
    if hard:
        # Remove only the chain file: the rest of .vantia/ (issue drafts,
        # artifacts, the registry index) must survive a hard reset too.
        if os.path.exists(chain.path):
            os.remove(chain.path)
        state.reset()
        HashChain().append({"event": "chain_genesis", "note": "hard reset"})
        registry = IdempotencyRegistry()
        if os.path.exists(registry.path):
            os.remove(registry.path)
        click.echo("hard reset: new state, new chain, registry wiped")
        return
    if not state.exists:
        raise click.ClickException(f"no state at {state.path}; run `vantia init` first")
    chain.append(
        {"event": "state_reset", "ts": utc_now(), "run_count": state.load().get("run_count")}
    )
    state.reset()
    registry = IdempotencyRegistry()
    if os.path.exists(registry.path):
        os.remove(registry.path)
        click.echo(f"registry wiped: {registry.path}")
    click.echo(f"state reseeded at {state.path} (chain len={HashChain().length})")


if __name__ == "__main__":  # pragma: no cover
    main()
