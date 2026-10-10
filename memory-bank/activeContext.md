# Active Context

## Current Focus
Session 12 (continuous loop). Run 16 closed **Phase 12 (6/6)**:
**64/88 tasks complete (73%)**, 540 tests / 94% coverage (5177 stmts) /
ruff+format+mypy green / web `next build` EXIT=0. The loop is now on
**run 17 — Phase 8 (User Workspaces)**: 8.1 Supabase Auth (`engine/auth/`,
JWT extract/refresh offline-verified), 8.2 profile + workspace tables
(`0004_workspaces.sql`), 8.3 RLS policies + JWT hook, 8.4 private file
storage, 8.5 workspace isolation E2E — all against an in-memory fake
Supabase (credentials stay `REPLACE_ME`). Queue afterwards: 6 → 5
(5.4–5.6) → 13 → 7, updating state + manifest + PLATFORM_STATE +
BUILD_BOARD + CHANGELOG + memory-bank each run.

## Recent Changes (session 12: runs 14 + 15 + 16)
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
1. Run 17 — Phase 8: 8.1 auth (`engine/auth/` JWT extract/refresh),
   8.2 `0004_workspaces.sql` profile + workspace tables, 8.3 RLS +
   JWT hook, 8.4 storage layer, 8.5 isolation E2E (offline fakes);
   close 5/5 (69/88).
2. Runs 18–21 per `docs/BUILD_BOARD.md` §2 until ship-ready.

## Known Issues
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