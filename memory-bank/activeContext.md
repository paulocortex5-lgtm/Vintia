# Active Context

## Current Focus
Session 1 (bootstrap + Phase 0 closeout). The engine and test suite were
already built and green in a prior working session but had never been
committed; this session established the tracking layer and pushed the
first commit.

## Recent Changes
- Created `PLATFORM_STATE.md` (master tracker, all 88 tasks, 14 phases).
- Created `memory-bank/` (6 files).
- Added `docs/RUNBOOK.md` (closes task 0.4).
- Created the `vantia-state` orphan branch with the authoritative state
  files (closes task 0.2).
- Baseline commit of the entire Phase 0 tree + test suite pushed to
  `origin/main`; state pushed to `origin/vantia-state`.
- Confirmed 96/96 unit tests pass, 97% engine line coverage.

## Next Steps
1. Task 1.5 — `engine/llm/providers.yaml` (12 free + 10 paid providers).
2. Task 1.6 — `engine/llm/router.py` + `engine/llm/quota.py`.
3. Task 1.7 — `engine/llm/client.py` + fence stripping + quota wiring.
Note: 1.1/1.2/1.3/1.4 and several Phase 9/10 schemas+prompts already
exist on disk ahead of schedule and should be verified/claimed before
work begins.

## Known Issues
- Supabase, Render, Vercel and Stripe credentials are `REPLACE_ME`
  placeholders — all network-success paths are untested.
- `engine/api.py` uses deprecated `@app.on_event("startup")`.
- The master prompt header claims 98 tasks, but the catalog actually
  lists 88 (state.json agrees with 88). Denominator is 88.
- Uncovered lines: supabase_client network-success paths and the
  keep_alive live ping-loop body (need credentials / a live server).