# Active Context

## Current Focus
Session 9 (continuous loop). Runs 9–11 closed: Phase 2 (9/9) and
Phase 3 (7/7) complete, **32/88 overall (36%)**. The loop now moves to
Phase 4 — verification & hardening — then Phases 5 → 6 → 9 → 10 →
11 → 12 → 8 → 13 → 7 (acceptance), updating state + manifest +
PLATFORM_STATE each run.

## Recent Changes
- `engine/credentials/` (2.4) — 28-row equivalence registry (UK FHEQ/
  NVQ, FR RNCP, DE DQR, Bologna, NG honest gaps), `lookup()` ranking
  with stopword-guarded coverage, `equivalence()` payload with
  target-country titles, `gpa_to_ects()` ratio bands, opt-in
  `remote_lookup()` on `Fetcher` via `VANTIA_EQUIVALENCE_ENDPOINT`
  (never a guessed URL). `eqf_level` only where verified.
- `engine/pipeline.py` (2.8) — `run_job_pipeline` wired: load_listing →
  active screen → fraud screen → register badge → `load_profile` →
  `generate_resume`; payload `{pipeline, job, fraud, sponsorship,
  resume}`.
- `engine/generators/profile.py` — `load_profile()` for `.json` /
  `.md` / `.txt` resumes with strict error codes.
- `tests/e2e/test_job_pipeline.py` (2.9) — 8 offline journeys on
  `MockTransport` with touched-host pinning.
- Suite: 28 files / 290 passing / 93% engine coverage; ruff + mypy
  clean (74 files). Manifest backfilled with runs 7–9.
- Commits: `bb8d7e3` (code), `ddbbfc7` (state); docs commit records
  session 9 in PLATFORM_STATE §10/§11.

## Next Steps
1. Phase 4: 4.1 domain verification (DNS + CNAME), 4.2 idempotency
   registry persistence, 4.3 cross-run hash chain, 4.4 circuit breaker
   + GitHub issue, 4.5 Supabase schema migration + RLS.
2. Phase 5 product surface; Phase 6 observability & deployment.
3. Phases 9 → 10 → 11 → 12 → 8 → 13 → 7 after that.

## Known Issues
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