# Active Context

## Current Focus
Run 22 (2026-10-14). **Phase 15 EXTENSION fully shipped: 104/104 tasks (100%)**,
828 tests passing / ruff+format+mypy green / web `next build` EXIT=0. All sixteen
extension features (15.1–15.16) built, committed, and pushed to `origin/main` +
`origin/vantia-state`. Country coverage is 54 countries with **JP as the only
Asian country and zero African countries** (per explicit user constraint). The
pre-existing `test_pipeline_links_every_step_it_promises` "launching soon"
assertion was flipped to `not in` per RULE 0.3 (conflict between R9 and R29;
zero-stub is the run's primary deliverable). No tasks remain.

## Recent Changes (session 12: runs 14–18)
- **Run 14 (Phase 10, `1003b3e`)**: reconciled board vs snapshot vs tree —
  the tree was ahead of both docs (all six tasks existed); suite run before
  recording. Recorded audit-verified 10.1/10.3; verified + wired 10.2
  (`engine/improve/cv.py`, fact-preserving edits, identity never
  model-owned) + 10.4 (`engine/generators/cover.py`, facts-only letters);
  10.5/10.6 offline E2E; every `.md` brought current.
- **Run 15 (Phase 11, `c1591d1`)**: built the credit system — append-only
  idempotent `CreditLedger` (+ `0002_credits.sql` balance tables, static
  parity-tested), `CreditMeter` (price from state, pre-flight before work,
  charge on completion), tiers (recorded-not-inferred, once-per-month
  allowance), `user_id` metering wired into 9.5/10.2/10.4,
  `GET /credits/balance` + `/credits/estimate`, offline credit-journey E2E;
  stale `ledger_pending` webhook stub test replaced with wired behavior;
  state run 15 + manifest appended.
- **Run 16 (Phase 12, `e9146e9`)**: audited PADDLE_SETUP against code
  (phantom `/api/*` paths fixed, dashboard return URLs documented);
  `POST /credits/checkout` (honest 502 without keys) + `POST /paddle/webhook`
  routes; `0003_paddle.sql` created the long-promised `paddle_events` table;
  `GET /credits/packs` + purchase page with the **first verified web build**
  (found + fixed the pre-existing sitemap `dynamic`/`cacheComponents`
  defect); engine CORS (`VANTIA_ALLOWED_ORIGINS`); env tier vars made real
  config overlays; offline purchase E2E; state run 16 + manifest appended.
- **Run 17 (Phase 8, `2b40f3c`)**: user workspaces — `engine/auth/`
  offline HS256 JWT verify + refresh (PyJWT now declared); `0004`/
  `0005` migrations (tables + 12 `auth.uid()` RLS policies + hardened
  tier-stamping JWT hook, static-tested, **not applied**);
  `WorkspaceService` ownership guard + `WorkspaceStorage`
  (validate-before-network, honest codes, `SupabaseClient.delete()`
  added); two-user isolation E2E (refused before zero storage calls);
  state run 17 + manifest appended.
- **Run 18 (Phase 6, `bb0b130`)**: observability & deployment — hash
  logging (`log_data` with sha256 pair on every chain append); public
  status page; Dockerfile digest-pinned + pip pinned + non-root;
  `render.yaml` (secrets `sync:false`) + `web/vercel.json` (`npm ci`);
  the four RUNBOOK-promised runbooks **that never existed** created
  (`RENDER_DEPLOY`, `VERCEL_DEPLOY`, `SUPABASE_SETUP` with 0001→0005
  rollout parity test, `KEEP_ALIVE`); `tests/test_deploy_configs.py`
  cross-config gate; state run 18 + manifest appended.

## Recent Changes (session 11: audit + run 13)
- **Audit** reconciled every conflicting claim: restored `PLATFORM_STATE.md`
  §3 rows/sessions from HEAD, reopened 5.4 (SEO unevidenced), backfilled
  5.1–5.3 with commits, adopted `web/` (`1efcae1`) and `docs/BUILD_BOARD.md`,
  appended manifest run 12, backfilled CHANGELOG runs 2–12.
- **Run 13 (Phase 9, `ba616fa`)**: `engine/ats/` rebuilt and tested —
  parser bugs fixed (`_strings` unbound crash, MIME-hint detection,
  extractor error wrapping), `scoring.py` rebuilt (12 categories = 100,
  demand detection, suggestion per sub-100 category), stemmer plural fix;
  `POST /ats/score` + `GET /status`; `run_ats_scan` (parse-before-network,
  traversal guard, `<file>.ats.json` persistence); offline E2E
  `tests/e2e/test_ats_journey.py`. Also fixed `start_run()` annotation and
  `domain.py` dnspython typing; repo-wide ruff/format/mypy sweep.
- State: run 13 + manifest recorded; commits `ba616fa` (code) →
  `d6f3287` (state) → docs.
- Security: the classic token pasted in chat was **not used**; it is
  compromised and must be rotated before any push.

## Next Steps
1. None — all 104 tasks complete. Phase 15 shipped.
2. Post-ship (optional hardening, non-blocking): `@app.on_event("startup")`
   lifespan migration; enable Google provider in the Supabase dashboard
   (Authentication → Providers → Google) if social sign-in is desired.

## Run 22 — web: session-gated tools + two-track pipeline (2026-10-13)
- `web/components/RequireSession.tsx` gates `/ats`, `/improve`,
  `/cover-letter`, `/credits/dashboard`, `/credits/purchase` (tools
  load `ssr: false`; marketing copy stays public). Purchase page now
  uses the verified session user id — typed placeholder removed.
- `/pipeline` page: job + scholarship tracks with honest live /
  launching-soon badges; linked from home, dashboard, `/jobs`,
  `/scholarships`; sitemap + `tests/test_web_pipeline.py` (6) added.
- Gates green: pytest web suites, `next build` EXIT=0.

## Known Issues
- **Google provider not enabled on the live Supabase project** (re-verified
  2026-10-13: `/auth/v1/authorize?provider=google` → 400 `Unsupported
  provider`) — Google sign-in cannot start until it is flipped in the
  Supabase dashboard (Authentication → Providers → Google; allowlist
  `…/auth/callback` under URL Configuration; docs/AUTH.md §3). No
  management PAT exists here to script it. The new `/api/auth/google`
  preflight now surfaces this refusal verbatim in-product instead of the
  raw JSON page (which also caused the favicon-404 console noise).
  Email/password, migration 0007 and engine CORS verified OK.
- Local dev: `web/.env.local` (git-ignored) carries the publishable
  NEXT_PUBLIC trio — Next reads env from `web/`, not the repo root;
  port 3000 on the dev machine is squatted by an unrelated server, so
  `next dev` starts on **3001** (allowlist that URL in Supabase).
- The 4.5 Supabase mirror schema is written and static-tested, but RLS
  policies and a real `supabase db push` are untested until real
  credentials exist — do not claim the migration as applied.
- Supabase, Render, Vercel and Paddle credentials are `REPLACE_ME`
  placeholders — all network-success paths are untested.
- No LLM API keys in this environment; every provider path is
  dry-run/MockTransport-verified only.
- `run_job_pipeline` loads by URL for W/G/L portals only; government
  listings need a detail loader (carried).
- ~~`engine/credits/ledger.py` does not exist~~ — **built in run 15**:
  Paddle top-ups now credit the balance (`credited`); `ledger_pending`
  remains only when a storage write itself fails.
- ~~Push to origin blocked~~ — **pushed 2026-10-10** (`6c7ccfd..8ef642e`)
  with the disclosed token under explicit user authorization; user rotates
  it at 100% build (inline `oauth2:` URL only, never written to the repo).
- `engine/api.py` uses deprecated `@app.on_event("startup")`.
- Header/master-prompt drift: PLATFORM_STATE says v6.0, seed says 4.0;
  denominator is 88 tasks.