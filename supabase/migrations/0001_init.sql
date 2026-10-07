-- ============================================================================
-- 0001_init.sql — Supabase/Postgres mirror of the Vantia bookkeeping state
-- (task 4.5: "State JSON → SQLite/Postgres schema draft (JSONB)".)
--
-- The canonical, git-committed state stays in `.vantia/state.json` + the
-- sha256 chain (§29).  This schema is the queryable mirror: sync it from the
-- engine with a plain INSERT ... ON CONFLICT, never hand-edit it.
--
-- Run order: psql "$DATABASE_URL" -f supabase/migrations/0001_init.sql
-- ============================================================================

begin;

-- ── runs ------------------------------------------------------------------
create table if not exists runs (
    id            integer  primary key,
    name          text     not null,
    status        text     not null default 'running'
                        check (status in ('running', 'complete', 'failed', 'blocked')),
    started_at    timestamptz,
    finished_at   timestamptz,
    note          text     not null default '',
    completed     integer  not null default 0,
    blocked       integer  not null default 0,
    skipped       integer  not null default 0,
    -- anything else the state manager stored for this run (raw JSON)
    payload       jsonb    not null default '{}'
);

-- ── tasks (rows of `runs[].tasks[]`) --------------------------------------
create table if not exists tasks (
    id          text     not null,           -- '0.1', '3.4', ...
    run_id      integer  not null references runs(id) on delete cascade,
    name        text     not null default '',
    status      text     not null default 'todo'
                    check (status in ('todo', 'in_progress', 'retry',
                                       'blocked', 'complete', 'skipped')),
    attempts    integer  not null default 0,
    artifact    text,
    payload     jsonb    not null default '{}',   -- error strings etc.
    updated_at  timestamptz not null default now(),
    primary key (id, run_id)
);

create index if not exists tasks_status_idx on tasks (status);
create index if not exists tasks_run_idx on tasks (run_id);

-- ── artifacts -------------------------------------------------------------
create table if not exists artifacts (
    task_id     text     not null references tasks (id, run_id) on delete cascade
                        deferrable initially deferred,
    run_id      integer  not null references runs(id) on delete cascade,
    path        text     not null,
    size_bytes  bigint,
    sha256      char(64),
    committed   boolean  not null default false,
    primary key (task_id, run_id, path)
);

create index if not exists artifacts_path_idx on artifacts (path);

-- ── idempotency registry (.vantia/idempotency_registry.json) --------------
create table if not exists idempotency_registry (
    task_key    char(64) primary key,     -- sha256 of the task key
    task_id     text     not null,
    status      text     not null default 'complete',
    artifacts   text[]   not null default '{}',
    entry_hash  char(64) not null,        -- tamper evidence, task 4.2
    at          timestamptz not null default now()
);

-- ── hash chain (.vantia/hash_chain.json) ----------------------------------
create table if not exists hash_chain (
    seq         bigint generated always as identity primary key,
    payload     jsonb    not null,
    prev_hash   char(64) not null,
    hash        char(64) not null unique,
    inserted_at timestamptz not null default now()
);

create index if not exists hash_chain_hash_idx on hash_chain (hash);

-- ── incidents (.vantia/issues/) -------------------------------------------
create table if not exists incidents (
    id          bigint generated always as identity primary key,
    title       text     not null,
    body        text     not null default '',
    method      text     not null default 'draft' check (method in ('gh', 'draft')),
    detail      text,                        -- gh output / issue url
    path        text,                        -- offline draft path
    at          timestamptz not null default now()
);

create index if not exists incidents_at_idx on incidents (at);

-- ── views the status page will query -------------------------------------
create view if not exists task_progress as
select count(*) filter (where status = 'complete')::int as completed,
       count(*) filter (where status = 'blocked')::int  as blocked,
       count(*) filter (where status = 'skipped')::int   as skipped,
       count(*)::int                                     as total
from tasks;

commit;