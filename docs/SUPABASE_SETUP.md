# Supabase Setup Runbook (task 6.6)

> **Status: NOT APPLIED.** This environment has no Supabase project —
> the five migrations ship in-repo, are static-tested
> (`tests/test_sql_schema.py`, `test_credits_sql.py`,
> `test_paddle_sql.py`, `test_workspaces_sql.py`), and are **never
> claimed as executed**. This runbook is the rollout procedure.

## 1. Create the project

1. <https://supabase.com> → New project (free tier).
2. Settings → API: copy into the backend env (Render) and `.env` locally:

   | Env var | Where it comes from |
   |---|---|
   | `SUPABASE_URL` | Project URL |
   | `SUPABASE_ANON_KEY` | anon/public key |
   | `SUPABASE_SERVICE_ROLE_KEY` | service_role key (**secret, server-only**) |
   | `SUPABASE_JWT_SECRET` | Settings → API → JWT Secret |

3. Never commit these values — they are `REPLACE_ME`/`sync: false`
   everywhere in the repo (see `.env.example`, `render.yaml`).

## 2. Apply the migrations, in numeric order

```bash
for f in supabase/migrations/00*.sql; do
  psql "$DATABASE_URL" -f "$f"
done
```

| File | What it creates |
|---|---|
| `0001_init.sql` | state mirror: runs, tasks, artifacts, idempotency_registry, hash_chain, incidents |
| `0002_credits.sql` | credit_balances + append-only credit_ledger |
| `0003_paddle.sql` | paddle_events delivery-dedupe log |
| `0004_workspaces.sql` | profiles, workspaces, workspace_files |
| `0005_rls.sql` | RLS on the three workspace tables + `vantia_jwt_hook` |

Each file is transactional (`begin; … commit;`) and idempotent
(`if not exists`), so re-running is safe.

## 3. Verify (run these after applying)

```sql
-- RLS is on and nothing is world-readable:
select relname, relrowsecurity from pg_class
 where relname in ('profiles','workspaces','workspace_files');
-- expect relrowsecurity = t for all three

select count(*) from pg_policies
 where schemaname = 'public'
   and tablename in ('profiles','workspaces','workspace_files');
-- expect 12

-- no permissive catch-all slipped in:
select count(*) from pg_policies
 where qual = 'true' and tablename in ('profiles','workspaces','workspace_files');
-- expect 0

-- the tier-stamping hook exists:
select proname from pg_proc where proname = 'vantia_jwt_hook';
```

## 4. Dashboard steps (cannot be scripted)

1. **Auth → Hooks → Custom Access Token Hook** → select
   `public.vantia_jwt_hook` so every JWT carries the profile `tier`.
2. **Storage → create bucket `user-workspaces` (private)** and add
   policies mirroring `0005_rls.sql`: the first path segment
   (`<user_id>/…`) must equal `auth.uid()`.
3. **Auth → Providers**: enable email (or GitHub) for sign-up; the engine
   only verifies tokens (`engine/auth/`), it never stores passwords.

## 5. Honesty rules

- A migration that ran locally but not on the shared project is **not**
  "applied" — re-run the verify queries above and paste their output into
  the release notes.
- The Supabase mirror in the engine is write-through and best-effort: git
  on `vantia-state` stays authoritative (§0.1 STEP K).
