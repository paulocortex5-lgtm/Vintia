# Active Context

## Current Focus
Session 10 (continuous loop). Runs 9–12 closed: Phase 2 (9/9), Phase 3
(7/7) and Phase 4 (5/5) complete, **37/88 overall (42%)**. The loop now
moves to Phase 5 — product surface — then Phases 6 → 9 → 10 →
11 → 12 → 8 → 13 → 7 (acceptance), updating state + manifest +
PLATFORM_STATE each run.

## Recent Changes
- `engine/verification/domain.py` (4.1) — DNS A/CNAME check against a
  provider expectation table (render/vercel CNAME targets) through an
  injectable resolver; `resolver_unavailable` reported **loudly** when
  `dnspython` is missing; `DomainReport` is JSON-serialisable for the
  status page.
- `engine/idempotency.py` (4.2) — every registry entry carries an
  `entry_hash` (SHA-256 over canonical JSON); `verify()` recomputes
  all and reports tampered **and** legacy unhashed entries;
  `entries()` added.
- `engine/hash_chain.py` (4.3) — `audit()` (ok/length/tip/
  first_bad_seq) and `record_run()`; run 12 is the first `run_finished`
  record in the cross-run chain.
- `engine/incidents.py` (4.4) — `open_issue` via `gh`; on failure the
  incident is written as an offline Markdown draft + index entry under
  `.vantia/issues/`. `StepExecutor._open_incident` is guarded so a
  failing reporter never masks the original block.
- `supabase/migrations/0001_init.sql` (4.5) — Postgres mirror of
  `.vantia/state.json` (runs, tasks, artifacts, idempotency_registry,
  hash_chain, incidents + `task_progress` view); sync is
  `INSERT ... ON CONFLICT`, never hand-edited.
- `engine/cli.py` — `status` reports chain audit + registry integrity
  and accepts `--verify-domain --domain … --expect …`.
- Suite: 35 files / 358 passing / 93% engine coverage (3484 stmts);
  ruff check + format and mypy clean (90 files).
- Commits: `b6a5cad` (code), `dbf0ef5` (state); docs commit records
  session 10 in PLATFORM_STATE §10/§11.

## Next Steps
1. Phase 5: 5.1 CLI golden tests, 5.2 web UI skeleton, 5.3 SEO, 5.4
   waitlist, etc. (Phases 0–4 closed: 37/88).
2. Phase 6 observability & deployment.
3. Phases 9 → 10 → 11 → 12 → 8 → 13 → 7 after that.

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
  `ledger_pending` until Phase 11.
- Push to origin blocked (HTTP 403) since session 3; commits are local
  and ready per `docs/RUNBOOK.md` inline-token procedure.
- `engine/api.py` uses deprecated `@app.on_event("startup")`.
- Header/master-prompt drift: PLATFORM_STATE says v6.0, seed says 4.0;
  denominator is 88 tasks.