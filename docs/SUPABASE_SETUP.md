# Supabase Setup Runbook (task 6.6)

> **Status: APPLIED (2026-10-12).** Project `zpzzrlxkmnmposdnxpeg` exists;
> migrations 0001→0007 are applied (all 17 tables answer via PostgREST),
> migrations 0008→0009 (ingest jobs, job recommendations) ship with run 21
> and are applied via the Management API in the deploy step,
> RLS verified live (anon INSERT into `profiles` → `42501` refusal),
> `vantia_jwt_hook` executes, bucket `user-workspaces` (private) created.
> **Remaining dashboard-only steps:** §4.1 (register the hook in Auth →
> Hooks) and §4.2 (storage policies mirroring the RLS migration) — neither is
> scriptable without a DB password or dashboard access.

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
| `0006_waitlist.sql` | waitlist double opt-in (pending/confirmed, sha256 token hash) |
| `0007_admin_role.sql` | `profiles.role` + first-Google-sign-in admin bootstrap (advisory-locked trigger) |
| `0008_ingest_jobs.sql` | `ingest.jobs` (link-verification columns) + `ingest.rejected_jobs` anti-predatory audit (tasks 15.2/15.3) |
| `0009_job_recommendations.sql` | `job_recommendations` 24h cache for CV-matched job lists (task 15.1) |
| `0010_sponsor_reliability.sql` | `sponsor_reliability` 0-100 employer trust scores (task 15.4) |
| `0011_pro_features.sql` | `cv_job_mappings`, `cv_refinement_turns`, `mock_interviews` for the Pro/gated LLM features (tasks 15.5/15.6/15.7) |
| `0012_applications.sql` | `applications` kanban board with job snapshots (task 15.8) |
| `0013_job_alerts.sql` | `job_alerts` saved-search subscriptions with digest windows (task 15.9) |
| `0014_referrals.sql` | `profiles.referral_code` + `referrals` two-sided credit log (task 15.11) |
| `0015_api_keys.sql` | `api_keys` hash-only keys for the public university API (task 15.12) |
| `0016_chat.sql` | `chat_conversations` + `chat_messages` with RLS keyed on `auth.uid()`::text = `user_id`; grants to `authenticated` (task 12.4 chatbot) |

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
