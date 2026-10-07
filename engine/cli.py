"""Vantia CLI.

Task 5.1 will extend this to the full ``apply / status / resume / verify
/ reset`` surface. This run ships the minimal commands so the ``vantia``
console script declared in ``pyproject.toml`` resolves:

* ``vantia init``    — materialise ``.vantia/state/state.json`` from the seed
* ``vantia status``  — summarise task states, next runnable tasks, hash chain
* ``vantia version`` — print the engine version

 ``status`` also reports chain audit (4.3), registry integrity (4.2) and,
 with ``--verify-domain``, the 4.1 DNS check.

"""

from __future__ import annotations

import json

import click

from . import __version__
from .hash_chain import HashChain
from .idempotency import IdempotencyRegistry
from .state_manager import VantiaState
from .verification.domain import verify_domain as check_domain


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="vantia")
def main() -> None:
    """Vantia — Universal Opportunity Engine."""


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


if __name__ == "__main__":  # pragma: no cover
    main()
