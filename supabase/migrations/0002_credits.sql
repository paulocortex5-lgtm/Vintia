-- ============================================================================
-- 0002_credits.sql — credit balances + append-only credit ledger (task 11.1)
--
-- Mirrors engine/credits/ledger.py exactly: the local ledger.json stays
-- authoritative (§0.1 STEP K), these tables are the queryable write-through
-- the engine upserts into. Replayed movements are no-ops in the engine, and
-- the composite primary key makes the mirror idempotent under PostgREST's
-- resolution=merge-duplicates too.
--
-- Run order: psql "$DATABASE_URL" -f supabase/migrations/0002_credits.sql
-- ============================================================================

begin;

-- ── balances (one row per user; a balance can never go negative) ────────
create table if not exists credit_balances (
    user_id      text    primary key,
    balance      integer not null default 0
                    check (balance >= 0),
    updated_at   text    not null default ''
);

-- ── ledger (append-only; movement idempotency key = (user_id, ref)) ─────
create table if not exists credit_ledger (
    user_id       text    not null,
    ref           text    not null,
    kind          text    not null
                        check (kind in ('topup', 'grant', 'spend', 'refund', 'adjustment')),
    amount        integer not null check (amount <> 0),
    balance_after integer not null check (balance_after >= 0),
    ts            text    not null,
    meta          jsonb   not null default '{}',
    primary key (user_id, ref)
);

create index if not exists credit_ledger_user_ts_idx
    on credit_ledger (user_id, ts desc);

commit;
