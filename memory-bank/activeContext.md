# Active Context

## Current Focus
Session 12 (continuous loop). Run 14 closed **Phase 10 (6/6)**:
**52/88 tasks complete (59%)**, 462 tests / 93% coverage (4807 stmts) /
ruff+format+mypy green. The loop is now on **run 15 — Phase 11 (Credit
System)**: `engine/credits/ledger.py` first (the Phase-11 dependency), then
token metering, tier enforcement, deduction on completion, balance API,
offline E2E. Queue afterwards: 12 → 8 → 6 → 5 (5.4–5.6) → 13 → 7, updating
state + manifest + PLATFORM_STATE + BUILD_BOARD + CHANGELOG + memory-bank
each run.

## Recent Changes (session 12: run 14)
- **Run 14 (Phase 10, `1003b3e`)**: reconciled board vs snapshot vs tree —
  the tree was ahead of both docs (all six tasks existed); suite run before
  recording. Recorded audit-verified 10.1/10.3; verified + wired 10.2
  (`engine/improve/cv.py`, fact-preserving edits, identity never
  model-owned) + 10.4 (`engine/generators/cover.py`, facts-only letters);
  10.5/10.6 offline E2E; state run 14 + manifest appended; every `.md`
  brought current.

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
1. Run 15 — Phase 11: `engine/credits/ledger.py` (11.1), token metering
   (11.2), tier definitions + enforcement (11.3), deduction on task
   completion (11.4), balance API + UI data (11.5), offline E2E (11.6);
   close 6/6 (58/88).
2. Runs 16–21 per `docs/BUILD_BOARD.md` §2 until ship-ready.

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
- `engine/credits/ledger.py` does not exist yet — Paddle top-ups stay
  `ledger_pending` until Phase 11 (run 15, **in flight**).
- Push to origin blocked: cached credential 403s since session 3, and
  the token disclosed in chat must be **rotated first**.
- `engine/api.py` uses deprecated `@app.on_event("startup")`.
- Header/master-prompt drift: PLATFORM_STATE says v6.0, seed says 4.0;
  denominator is 88 tasks.