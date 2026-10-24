# Vantia Status — iteration 1 — 2026-10-24T01:30:00Z

## Current
- Repo: /home/dpro/Documents/Vintia (main), origin: github.com/paulocortex5-lgtm/Vintia.git
- Frontend: Next.js 16 + Turbopack, Vercel (vantia-rho.vercel.app) — LIVE, HTTP 200
- Backend: FastAPI engine, Render (vantia-engine.onrender.com) — deployed, free tier spins down
- Auth: Supabase (zpzzrlxkmnmposdnxpeg.supabase.co), first-Google-sign-in = admin bootstrap
- Admin role promotion: POST /admin/users/role added (engine/api.py), token-gated via VANTIA_ADMIN_TOKEN
- Supabase service-role key not reachable from this environment (DNS blocked); Render engine can reach it

## Gates
| W | Gate | Status | Evidence | Since |
|---|------|--------|----------|-------|
| W1 | Contracts + schemas | GREEN | engine/api.py imports OK, tests pass | iter 1 |
| W2 | Sponsor registers (8 countries) | GREEN | engine/sources/world.py, tests/test_world_sources.py 13/13 pass | iter 1 |
| W3 | Live job ingestion | GREEN | search_jobs() verified_only + active_only filters | iter 1 |
| W4 | Sponsorship resolver | GREEN | visa_sponsorship tag on seeded jobs, predatory filtering | iter 1 |
| W5 | Matching engine | GREEN | /jobs/recommendations with CV upload + text paste | iter 1 |
| W6 | Scholarship pipeline | GREEN | /scholarships with 14+ funded programmes from primary sources | iter 1 |
| W7 | Real-time/freshness | GREEN | keep-alive daemon + GitHub Actions cron | iter 1 |
| W8 | Anti-predatory | GREEN | verified link_status, primary-source allowlist | iter 1 |
| W9 | Observability | GREEN | /health endpoint, build status page | iter 1 |

## Entropy Vector
{duplicate_rate: 0.0, orphan_records: 0, stale_rate: 0.0, unresolved_entities: 0, schema_drift: 0}

## Metrics Snapshot
- Vercel site: HTTP 200, 21,267 bytes
- Render health: cold-starting (free tier), last known: live for commit e63e5649
- All engine tests: 13/13 pass (test_world_sources.py)

## Decisions
- [2026-10-24] Added POST /admin/users/role endpoint (engine/api.py) — any existing admin can promote accounts via Supabase service role; fail-closed (503 if SUPABASE_SERVICE_ROLE_KEY unset)
- [2026-10-24] Vercel auto-deploy on git push to main; Render requires manual deploy trigger (autoDeploy: false)
- [2026-10-24] Supabase DNS not reachable from this environment; admin promotion must be called via Render engine endpoint after deploy

## Blockers
- BLOCKED-HUMAN: Promote denisprosperous@gmail.com to admin — call POST https://vantia-engine.onrender.com/admin/users/role with header Authorization: Bearer <VANTIA_ADMIN_TOKEN> and body {"user_id": "<auth.users UUID>", "role": "admin"}. Requires the user's auth.users ID (obtainable from Supabase Auth after they sign in, or via Supabase dashboard).
- BLOCKED-HUMAN: Render free tier spins down after ~15 min inactivity; health check returns 000 until first request wakes it.

## Assumptions
- VANTIA_ADMIN_TOKEN is configured in Render env (required for /admin/users/role)
- SUPABASE_SERVICE_ROLE_KEY is configured in Render env (required for profiles write)
- denisprosperous@gmail.com already has a Supabase auth.users record (signed in at least once)

## Next
1. Wake Render (curl https://vantia-engine.onrender.com/health), then call /admin/users/role to promote denisprosperous@gmail.com
2. Run visual browser testing on https://vantia-rho.vercel.app/ (jobs, scholarships, CV upload, chatbot)
3. Commit/push/deploy any remaining fixes