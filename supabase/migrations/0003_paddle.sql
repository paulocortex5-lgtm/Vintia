-- ============================================================================
-- 0003_paddle.sql — Paddle webhook event log (tasks 12.3 / 12.4)
--
-- The webhook's R50 idempotency lookup ("SELECT from paddle_events WHERE
-- event_id = ?" in docs/PADDLE_SETUP.md §4) needs a durable row store.
-- The engine's local ledger keeps money correct on its own (ref idempotency);
-- this table is the queryable dedupe/audit trail of *deliveries*.
-- Column names mirror exactly what engine/credits/paddle_webhook.py upserts.
--
-- Run order: psql "$DATABASE_URL" -f supabase/migrations/0003_paddle.sql
-- ============================================================================

begin;

create table if not exists paddle_events (
    event_id     text    primary key,
    event_type   text    not null default '',
    occurred_at  text    not null default '',
    user_id      text    not null default '',
    credits      integer not null default 0
                     check (credits >= 0),
    status       text    not null default 'recorded'
                     check (status in ('recorded', 'credited', 'ledger_pending', 'already_processed')),
    ledger_state text    not null default 'not_required'
                     check (ledger_state in ('not_required', 'ok', 'failed', 'unavailable')),
    processed_at text    not null default '',
    data         jsonb   not null default '{}'
);

create index if not exists paddle_events_user_idx on paddle_events (user_id);

commit;
