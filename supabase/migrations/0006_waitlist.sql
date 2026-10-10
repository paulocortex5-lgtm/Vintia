-- ============================================================================
-- 0006_waitlist.sql — waitlist with double opt-in (task 5.6)
--
-- A subscriber is only ever `pending` until the emailed token is redeemed;
-- `token_hash` stores SHA-256 of the token, never the token itself, so a
-- database leak cannot confirm anyone. Engine-side writes use the service
-- role; the table is not exposed for user reads.
--
-- Run order: psql "$DATABASE_URL" -f supabase/migrations/0006_waitlist.sql
-- ============================================================================

begin;

create table if not exists waitlist (
    email        text    primary key,
    status       text    not null default 'pending'
                         check (status in ('pending', 'confirmed')),
    token_hash   text    not null,
    created_at   text    not null default '',
    confirmed_at text    not null default ''
);

create index if not exists waitlist_status_idx on waitlist (status);

commit;
