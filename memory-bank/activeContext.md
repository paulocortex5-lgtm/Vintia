# Active Context

## Current Focus
Session 11 (audit → continuous loop). The audit reconciled every
conflicting claim: **40/88 tasks complete (45%)**, Phases 0–4 closed,
Phase 5 at 3/6 (5.4 reopened — no schema.org evidence). The loop is
now on **run 13 — Phase 9 (ATS scoring)**: repair the broken
`engine/ats/scoring.py`, test 9.1/9.3, then 9.4 schema+API, 9.5
`run_ats_scan`, 9.6 E2E. Queue afterwards: 10 → 11 → 12 → 8 → 6 →
5 (5.4–5.6) → 13 → 7, updating state + manifest + PLATFORM_STATE +
BUILD_BOARD + CHANGELOG + memory-bank each run.

## Recent Changes (session 11 audit)
- `PLATFORM_STATE.md` — restored from HEAD `6c7ccfd` (a local edit
  had reverted §3 rows for Phases 2–5 to ⏳ and deleted §10 sessions
  1/2/5–9), then applied only verified updates: §1/§2 metrics,
  Phase 5 rows (5.1/5.2 → `9775b07`, 5.3 → `1efcae1`), §6 counts
  (381 passing, 93% coverage excluding `engine/ats`), §7 audit row
  for 5.4, §9 commit rows, §10 sessions 10–11, §11 queue, §12
  token-rotation risk.
- `.vantia/state/state.json` — 5.4 reopened to pending; 5.1–5.3
  backfilled with commit SHAs + artifacts; `last_completed_task=5.3`.
- `.vantia/run_manifest.json` — run 12 appended (it had never been
  recorded).
- `web/` adopted as task 5.3 (`1efcae1`); `docs/BUILD_BOARD.md`
  adopted as the live in-flight/queue view with the full audit table.
- `CHANGELOG.md` backfilled runs 2–12; memory-bank brought current.
- Security: the classic token pasted in chat was **not used**; it is
  compromised and must be rotated before any push.

## Next Steps
1. Run 13 — Phase 9: fix `engine/ats/scoring.py`, tests for parser/
   keywords/scoring, `POST /ats/score` + `/status`, `run_ats_scan`,
   E2E; close 9.1–9.6 (46/88).
2. Runs 14–21 per `docs/BUILD_BOARD.md` §2 until ship-ready.

## Known Issues
- `engine/ats/scoring.py` is syntactically broken until run 13 lands
  (9.1/9.3 also untested) — the suite passes only because nothing
  imports `engine.ats` yet.
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
  `ledger_pending` until Phase 11 (run 15).
- Push to origin blocked: cached credential 403s since session 3, and
  the token disclosed in chat must be **rotated first**.
- `engine/api.py` uses deprecated `@app.on_event("startup")`.
- Header/master-prompt drift: PLATFORM_STATE says v6.0, seed says 4.0;
  denominator is 88 tasks.