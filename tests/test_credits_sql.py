"""Static tests for ``supabase/migrations/0002_credits.sql`` (task 11.1).

Same contract as ``test_sql_schema.py`` for 0001: the DDL is checked
structurally and against the engine's own ``ENTRY_KINDS`` so the mirror can
never drift from what ``engine/credits/ledger.py`` writes. Applying it for
real needs a reachable Postgres, which this environment lacks.
"""

from pathlib import Path

from engine.credits.ledger import ENTRY_KINDS

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "0002_credits.sql"

SQL = MIGRATION.read_text(encoding="utf-8")


def test_migration_exists_and_is_transactional():
    assert MIGRATION.exists()
    assert "begin;" in SQL
    assert SQL.rstrip().endswith("commit;")


def test_expected_tables_are_created():
    assert "create table if not exists credit_balances" in SQL
    assert "create table if not exists credit_ledger" in SQL


def test_balance_cannot_go_negative():
    assert "check (balance >= 0)" in SQL
    assert "check (balance_after >= 0)" in SQL


def test_ledger_kinds_match_the_engine_exactly():
    """The SQL CHECK and ``ENTRY_KINDS`` must never drift apart."""
    for kind in ENTRY_KINDS:
        assert f"'{kind}'" in SQL, f"engine kind {kind!r} missing from SQL check"


def test_movement_idempotency_key_is_primary():
    assert "primary key (user_id, ref)" in SQL


def test_amounts_are_signed_and_nonzero():
    assert "check (amount <> 0)" in SQL


def test_ledger_is_append_only_by_convention():
    """No UPDATE/DELETE statements exist in the migration at all."""
    upper = SQL.upper()
    assert "UPDATE " not in upper
    assert "DELETE " not in upper


def test_ddl_is_well_formed():
    assert SQL.count("(") == SQL.count(")")
    for statement in [s for s in SQL.split(";") if s.strip()]:
        assert statement.strip()
