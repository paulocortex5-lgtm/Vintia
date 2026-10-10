-- ============================================================================
-- 0004_workspaces.sql — user profiles, workspaces, workspace files (task 8.2)
--
-- Tenancy model: every row carries a text user_id matching the auth JWT's
-- `sub` claim (engine auth uses text ids end-to-end, including the credit
-- ledger). Row-level security (0005_rls.sql) scopes every read/write to
-- `auth.uid()`; the engine acts with the service role as trusted backend.
--
-- Run order: psql "$DATABASE_URL" -f supabase/migrations/0004_workspaces.sql
-- ============================================================================

begin;

-- ── profiles (one row per authenticated user) ──────────────────────────
create table if not exists profiles (
    user_id      text    primary key,
    email        text    not null default '',
    display_name text    not null default '',
    tier         text    not null default 'free'
                         check (tier in ('free', 'pro', 'business')),
    created_at   text    not null default '',
    updated_at   text    not null default ''
);

-- ── workspaces (owned by exactly one profile) ──────────────────────────
create table if not exists workspaces (
    workspace_id text    primary key,
    user_id      text    not null references profiles(user_id) on delete cascade,
    name         text    not null default 'default',
    created_at   text    not null default ''
);

create index if not exists workspaces_user_idx on workspaces (user_id);

-- ── workspace_files (metadata mirror of Storage objects) ────────────────
create table if not exists workspace_files (
    file_id      text    primary key,
    workspace_id text    not null references workspaces(workspace_id) on delete cascade,
    filename     text    not null,
    size_bytes   integer not null default 0 check (size_bytes >= 0),
    content_type text    not null default '',
    storage_path text    not null default '',
    created_at   text    not null default '',
    unique (workspace_id, filename)
);

create index if not exists workspace_files_ws_idx on workspace_files (workspace_id);

commit;
