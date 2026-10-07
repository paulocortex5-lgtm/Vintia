# Progress

## What Works
- Phase 0 scaffold: pyproject, requirements, Dockerfile, 3 GitHub
  Actions workflows (keep-alive cron `*/14 * * * *` verified), docs.
- Core engine modules all import cleanly; state_manager, locking,
  idempotency, hash_chain, json_utils, cost_tracker, logging_config,
  errors, retry, execute_step, pipeline, api, keep_alive, cli,
  persistence (supabase_client + fallback).
- **Phase 1 complete (7/7):** schemas (envelope, ATS, SOP, research
  proposal), prompt templates v1, LLM stack (providers.yaml — 22
  providers, free-first failover router, quota tracker, client with
  dry-run / cost ceiling / hash-chained envelopes).
- **Phase 2 complete (9/9):** fetch base (robots + rate limit), W/G/L
  portal adapters, all-country sponsor registers (GB CSV live, AU
  pending, 50-European dispatch), credential equivalence (28-row
  sourced registry, GPA→ECTS, ENIC-NARIC advice on gaps), fraud +
  injection/PII guardrails, ATS resume generator,
  `run_job_pipeline` wired end to end, offline E2E (MockTransport).
- Suite: 28 test files / **290 passing** / 93% line coverage of
  `engine/`; `ruff check`, `ruff format --check` and `mypy` clean
  (74 files).
- **Phase 4 complete (5/5):** `engine/verification/domain.py`
  (DNS A/CNAME with provider expectation table, injectable resolver),
  tamper-evident `engine/idempotency.py` (per-entry `entry_hash`,
  `verify()` — "unverifiable ≠ verified"), cross-run
  `engine/hash_chain.py` (`audit()` + `record_run()`),
  `engine/incidents.py` (GitHub issue via `gh`, offline Markdown draft
  fallback so no incident is lost), `supabase/migrations/0001_init.sql`
  (Postgres mirror of the bookkeeping state). `vantia status` now
  reports chain audit + registry integrity and accepts
  `--verify-domain`.
- Suite: 35 test files / **358 passing** / 93% line coverage of
  `engine/` (3484 stmts); `ruff check`, `ruff format --check` and
  `mypy` clean (90 files).
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
Phase 2 (run 9), Phase 3 (runs 10–11) and Phase 4 (run 12) closed:
**37/88 tasks**, 35 test files / 358 passing / 93% coverage. Next:
Phase 5 — product surface (5.1–5.6).

## Blockers
- None hard. Real provider/infrastructure credentials (Supabase,
  Render, Vercel, Paddle) are placeholders, which defers all
  network-success verification until launch prep.
- GitHub credential must never be written into the repository; pushes
  use an inline `oauth2:<token>@github.com/...` URL.