"""Tests for ``supabase/migrations/0001_init.sql`` (task 4.5).

Static checks: every table the engine needs exists, statuses are
constrained, JSONB carries the raw state, and the DDL is syntactically
well formed (balanced parentheses, `;`-terminated statements).  Applying
it for real needs a reachable Postgres, which this environment lacks.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "0001_init.sql"

SQL = MIGRATION.read_text(encoding="utf-8")

EXPECTED_TABLES = [
    "runs",
    "tasks",
    "artifacts",
    "idempotency_registry",
    "hash_chain",
    "incidents",
]

ENGINE_TASK_STATUSES = ("todo", "in_progress", "retry", "blocked", "complete", "skipped")
ENGINE_RUN_STATUSES = ("running", "complete", "failed", "blocked")


def test_migration_exists_and_is_transactional():
    assert MIGRATION.exists()
    assert "begin;" in SQL
    assert SQL.rstrip().endswith("commit;")


def test_expected_tables_are_created():
    for table in EXPECTED_TABLES:
        assert f"create table if not exists {table}" in SQL, table


def test_task_statuses_match_the_engine_state():
    for status in ENGINE_TASK_STATUSES:
        assert status in SQL, f"task status {status!r} missing from check()"


def test_run_statuses_match_the_engine_state():
    for status in ENGINE_RUN_STATUSES:
        assert status in SQL, f"run status {status!r} missing from check()"


def test_jsonb_carries_the_raw_state():
    assert "jsonb" in SQL
    assert "payload" in SQL


def test_tamper_evidence_column_is_present():
    assert "entry_hash" in SQL  # idempotency registry (task 4.2)
    assert "char(64)" in SQL  # sha256 columns


def test_ddl_is_well_formed():
    assert SQL.count("(") == SQL.count(")"), "unbalanced parentheses"
    body = "\n".join(line for line in SQL.splitlines() if not line.strip().startswith("--"))
    statements = [part.strip() for part in body.split(";") if part.strip()]
    assert statements, "no statements"
    for statement in statements:
        assert not statement.rstrip().endswith("("), statement[:80]
        assert statement[0].islower(), statement[:40]  # sql keywords only


def test_progress_view_exposes_counts():
    # Postgres rejects `create view if not exists` (SQLSTATE 42601); the
    # idempotent spelling is `create or replace view`. Comments are stripped
    # first so the explanatory comment naming the broken form doesn't trip
    # the negative assertion.
    body = "\n".join(line for line in SQL.splitlines() if not line.strip().startswith("--"))
    assert "create or replace view task_progress" in body
    assert "create view if not exists" not in body
    for column in ("completed", "blocked", "skipped", "total"):
        assert column in SQL


def test_artifacts_fk_is_composite_over_the_tasks_primary_key():
    """A single-column ``references tasks (id, run_id)`` is SQLSTATE 42830.

    ``tasks``' primary key is ``(id, run_id)``; Postgres rejects an FK that
    lists two referenced columns but one referencing column. Caught on the
    first real ``supabase db push`` (2026-10-11) — this pins the fix.
    """
    assert "constraint artifacts_task_fk" in SQL
    assert "foreign key (task_id, run_id) references tasks (id, run_id)" in SQL
    # the broken column-level form must not come back
    assert "task_id     text     not null references tasks" not in SQL
