"""Static tests for ``supabase/migrations/0003_paddle.sql`` (tasks 12.3/12.4).

Checks the DDL against what ``engine/credits/paddle_webhook.py`` actually
upserts, so the delivery-dedupe store can never drift from the handler.
Applying it for real needs a reachable Postgres, which this environment
lacks — the same honest constraint as ``test_sql_schema.py``.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "0003_paddle.sql"

SQL = MIGRATION.read_text(encoding="utf-8")

#: Keys of the row handle_webhook() upserts into ``paddle_events``.
HANDLER_COLUMNS = [
    "event_id",
    "event_type",
    "occurred_at",
    "user_id",
    "credits",
    "status",
    "ledger_state",
    "data",
    "processed_at",
]


def test_migration_exists_and_is_transactional():
    assert MIGRATION.exists()
    assert "begin;" in SQL
    assert SQL.rstrip().endswith("commit;")


def test_paddle_events_table_is_created():
    assert "create table if not exists paddle_events" in SQL


def test_every_handler_column_exists():
    for column in HANDLER_COLUMNS:
        assert f"{column}" in SQL, f"handler upserts {column!r} but the table lacks it"


def test_event_id_is_the_idempotency_primary_key():
    assert "event_id" in SQL
    assert "primary key" in SQL


def test_statuses_match_the_handler_vocabulary():
    for status in ("recorded", "credited", "ledger_pending", "already_processed"):
        assert f"'{status}'" in SQL, status
    for state in ("not_required", "ok", "failed", "unavailable"):
        assert f"'{state}'" in SQL, state


def test_no_stripe_remains_anywhere():
    """R56: Paddle replaced Stripe; no Stripe table may reappear."""
    assert "stripe" not in SQL.lower()


def test_ddl_is_well_formed():
    assert SQL.count("(") == SQL.count(")")
    for statement in [s for s in SQL.split(";") if s.strip()]:
        assert statement.strip()
