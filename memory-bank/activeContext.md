# Active Context

## Current Focus
Session 3 (Phase 1 LLM core + Stripe→Paddle purge). The LLM stack
(1.5 / 1.6 / 1.7) and the mandatory payment-provider migration (task 0.0)
are implemented, tested and lint-clean; the repo is ready for the
remaining Phase 1 work — schemas and prompts (1.1–1.4).

## Recent Changes
- `engine/llm/providers.yaml` — 22 providers (12 free / 10 paid) across
  four payload styles; adding a provider is a YAML edit only (R38).
- `engine/llm/router.py` — registry parsing, API-key and quota
  filtering, `pick()` free-before-paid ordering (R27), `registry_for()`
  per-path cache.
- `engine/llm/quota.py` — `QuotaTracker`: daily rollover, rpd/rpm caps,
  JSON cache as the offline source of truth, optional Supabase mirror.
  `usage_snapshot()` self-deadlocked on a non-reentrant lock; switched to
  `threading.RLock`.
- `engine/llm/client.py` — `LLMClient.complete()` / `run_chain()`
  failover, dry-run with zero network I/O (R25), cost ceiling (R18),
  hash-chained envelopes (R24). `engine/json_utils.py` gained
  `strip_fences`, `canonical_json` and `safe_parse`.
- Task 0.0: every `STRIPE_*` reference removed from code, config, docs
  and memory-bank; added `PaddleError`,
  `engine/credits/paddle_client.py`, `engine/credits/paddle_webhook.py`
  (HMAC-SHA256, 5 s replay window, `paddle_events` idempotency) and
  `docs/PADDLE_SETUP.md`.
- New test files: `test_llm_router.py`, `test_quota.py`,
  `test_llm_client.py`, `test_json_utils.py`, `test_paddle_webhook.py`.
- Suite now: 18 files / 165 passing / 91% `engine/` line coverage.

## Next Steps
1. Task 1.1 — envelope + ATS schema (`engine/schemas/`).
2. Task 1.2 — SOP schema; 1.3 — research proposal schema.
3. Task 1.4 — prompt templates v1 (`engine/prompts/v1_*.md`).
Note: 1.1/1.2/1.3/1.4 files already exist on disk ahead of schedule and
should be verified/claimed before new work begins.

## Known Issues
- Supabase, Render, Vercel and Paddle credentials are `REPLACE_ME`
  placeholders — all network-success paths are untested.
- `engine/api.py` uses deprecated `@app.on_event("startup")`.
- The master prompt header claims 98 tasks, but the catalog actually
  lists 88 (state.json agrees with 88). Denominator is 88.
- Uncovered lines: supabase_client network-success paths and the
  keep_alive live ping-loop body (need credentials / a live server).
- `engine/credits/ledger.py` does not exist yet, so Paddle top-ups are
  recorded with status `ledger_pending` (no balance change) until Phase
  11 wires in `topup_from_paddle`.
- Pre-existing ruff/mypy debt in modules untouched by the LLM/Paddle
  work (api.py, execute_step.py, retry.py, state_manager.py,
  test_execute_step.py); new code is `ruff check` + `ruff format` clean.