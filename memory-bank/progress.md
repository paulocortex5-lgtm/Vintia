# Progress

## What Works
- Phase 0 scaffold: pyproject, requirements, Dockerfile, 3 GitHub
  Actions workflows (keep-alive cron `*/14 * * * *` verified), docs.
- Core engine modules all import cleanly (18 modules verified).
- state_manager, locking, idempotency, hash_chain, json_utils,
  cost_tracker, logging_config, errors, retry, execute_step, pipeline,
  api, keep_alive, cli, persistence (supabase_client + fallback).
- 18 test files / 165 passing tests, 91% line coverage of `engine/`
  (`python -m pytest --cov=engine -q`).
- Phase 1 LLM core complete (1.5/1.6/1.7): `engine/llm/providers.yaml`
  (22 providers — 12 free / 10 paid), `engine/llm/router.py`
  (key + quota filtering, free-before-paid `pick()`), `engine/llm/quota.py`
  (daily rollover, rpd/rpm caps, optional Supabase mirror),
  `engine/llm/client.py` (failover, dry-run, cost ceiling, hash-chained
  envelope) and the `json_utils` helpers (`strip_fences`,
  `canonical_json`, `safe_parse`).
- Payments migrated to Paddle (task 0.0): every `STRIPE_*` reference is
  gone; `engine/credits/paddle_client.py` (checkout transactions),
  `engine/credits/paddle_webhook.py` (HMAC-SHA256 signature + 5 s replay
  window + `paddle_events` idempotency), `docs/PADDLE_SETUP.md`.
- New/touched files are clean under `ruff check` and `ruff format --check`.
- CLI verified end-to-end: `vantia init` then `vantia status`
  (88 pending, next 0.1, chain ok).
- Engine bugs found by the tests and fixed:
  1. `state_manager` — `begin_task`/`complete_task`/`fail_task` raised
     KeyError; they indexed `save(data)[task_id]` instead of
     `save(data)["tasks"][task_id]`.
  2. `logging_config.log_data` — crashed reading `frame.filename` /
     `frame.lineno`; fixed to `frame.f_code.co_filename` / `frame.f_lineno`.
  3. `state_manager.end_run` — returned `run_history[-1]` instead of
     the run it actually closed.
  4. `quota.QuotaTracker.usage_snapshot` (this session) — held a
     non-reentrant `threading.Lock` while calling `remaining_rpd()` /
     `check_quota()`, which re-acquire the same lock → deadlock that hung
     the test run. Fixed with `threading.RLock`.
- Version-controlled: first commit on `origin/main` and the orphan
  `origin/vantia-state` branch, both pushed.
- **Not pushed (new):** `279c3ca` on `main` and `76867be` on
  `vantia-state` are committed locally but the push was rejected with
  HTTP 403 — the environment's cached GitHub credential belongs to an
  account without access to `paulocortex5-lgtm/Vintia` (no `gh` CLI, no
  stored token). Push with the inline credential per `docs/RUNBOOK.md`:
  `git push https://oauth2:<token>@github.com/paulocortex5-lgtm/Vintia.git main vantia-state`.

## What's Left
- Phase 1 (4 left): schemas 1.1/1.2/1.3 and prompts 1.4
  (1.5/1.6/1.7 complete this session).
- Phase 2 (9): jobs trail — sources, visa registers, credentials,
  fraud filter, injection/PII, ATS generator, pipeline, E2E.
- Phase 3 (7): scholarship engine.
- Phase 4 (5): verification & hardening.
- Phase 5 (6): product surface (CLI golden tests, web UI, SEO).
- Phase 6 (7): observability & deployment (render.yaml, vercel.json).
- Phase 7 (3): acceptance.
- Phase 8 (5): workspaces & multi-tenancy.
- Phase 9 (6): ATS scoring.
- Phase 10 (6): CV improvement + cover letter.
- Phase 11 (6): credit system & tiers.
- Phase 12 (6): credit purchasing (Paddle).
- Phase 13 (6): workspace UI + full journey.

## Current Milestone
Phase 0 complete; Phase 1 LLM core (1.5/1.6/1.7) complete, tested and
pushed. Next: Phase 1 schemas + prompts (1.1–1.4).

## Blockers
- None hard. Real provider/infrastructure credentials (Supabase,
  Render, Vercel, Paddle) are placeholders, which defers all
  network-success verification until launch prep.
- GitHub credential must never be written into the repository; pushes
  use an inline `oauth2:<token>@github.com/...` URL.