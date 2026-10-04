# System Patterns

## Backend Architecture
- FastAPI async app with /health, /status, /metrics, /api/* routes
- Engine modules under engine/ organized by domain
- Idempotency keys prevent duplicate LLM calls across runs
- Hash chain ensures artifact integrity across sessions
- Multi-provider LLM router with automatic failover

## Frontend Architecture
- Next.js 14 app router with server + client components
- Supabase Auth for session management
- Client-side file uploads to Supabase Storage for files > 4.5 MB
- Tailwind + shadcn/ui for consistent styling

## Data Isolation
- Row Level Security on every tenant table
- JWT materializes workspace_id claim via Custom Access Token Hook
- Storage bucket policies enforce per-workspace folder access
- Service role key used only server-side for engine operations

## Credit System
- Every LLM call deducts tokens from user balance
- Insufficient balance blocks the call with InsufficientCredits error
- Monthly reset via GitHub Actions cron on the 1st of each month
- Paddle webhook idempotency via event_id

## State & Branch Model (Vantia-specific, established Session 1)
- `.vantia/` is gitignored on `main`; it is intentionally excluded from
  the application branch so the runtime state never ships in a deploy.
- The authoritative state, artifacts, hash chain and idempotency
  registry are tracked ONLY on the orphan branch `vantia-state`.
- Because `.vantia/` is ignored on main, staging it requires
  `git add -f .vantia/...`.
- Git is the authoritative audit trail; Supabase is primary persistence.
- Fail-safe invariants (asserted by tests): a corrupt lock file is
  REFUSED (left untouched), never stolen; corrupt registry/state files
  fail loudly rather than being silently repaired.