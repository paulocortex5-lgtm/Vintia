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
- **Phase 3 complete (7/7):** scholarship database (5 sourced
  programs), SOP + research proposal generators, credential mapper,
  window tracker, `run_scholarship_pipeline`, offline E2E.
- **Phase 4 complete (5/5):** domain verification, tamper-evident
  idempotency, cross-run hash-chain audit, incident reporter
  (offline draft fallback), `supabase/migrations/0001_init.sql`.
- **Phase 5 (3/6, audited session 11):** full CLI surface
  (`init/apply/status/resume/verify/reset`, commit `9775b07`) with
  golden-file tests; `web/` Next.js skeleton adopted (`1efcae1`)
  incl. a static sitemap route. 5.4 (SEO) was claimed but **not**
  evidenced → reopened; 5.5/5.6 pending.
- **Phase 9 complete (6/6, run 13 `ba616fa`):** `engine/ats/` — resume
  parser (PDF/DOCX/TXT/MD/JSON, honest confidence, loud failures),
  twelve-point deterministic rubric with demand detection, keyword
  matcher + gap report; `POST /ats/score` + `GET /status`;
  `run_ats_scan` (parse-before-network, traversal guard, report
  persisted); offline E2E with touched-host pin.
- **Phase 10 complete (6/6, run 14 `1003b3e`):** `engine/improve/cv.py`
  (deterministic fact-preserving CV edits, ≤30 ranked, identity never
  model-owned) + `engine/generators/cover.py` (facts-only letters,
  verbatim quantified bullets, no invented achievements); `run_cv_improvement`
  + `run_cover_letter` wired (store resolution, traversal guard, closed-
  listing refusal); prompts/schemas audit-verified; offline E2E ×2.
- **Phase 11 complete (6/6, run 15 `c1591d1`):** credit system —
  append-only idempotent `CreditLedger` + `0002_credits.sql` balance
  tables; `CreditMeter` (prices from state, pre-flight before work,
  charge on completion only); free/pro/business tiers with once-per-month
  allowance + R46 enforcement; `user_id` metering on the ATS/CV-improvement/
  cover-letter pipelines; `GET /credits/balance` + `/credits/estimate`;
  offline credit-journey E2E (refusal with zero network calls, webhook
  double-delivery credits exactly once).
- Suite (run 16, 2026-10-10): 55 test files / **540 passing** /
  **94% line coverage of `engine/`** (5177 stmts; api.py 97%);
  `ruff check`, `ruff format --check` and `mypy` clean repo-wide;
  **web `next build` EXIT=0** (first build gate — fixed the pre-existing
  sitemap `dynamic`/`cacheComponents` conflict).
- **Phase 12 complete (6/6, run 16 `e9146e9`):** credit purchasing —
  PADDLE_SETUP audited + corrected; `POST /credits/checkout` (stable 422
  codes, honest 502 without keys) + `POST /paddle/webhook` route;
  `0003_paddle.sql` `paddle_events` dedupe table; `GET /credits/packs` +
  `web/app/credits/purchase/page.tsx` + CORS (`VANTIA_ALLOWED_ORIGINS`);
  offline purchase E2E; env tier vars wired as real config overlays.
- Payments migrated to Paddle (task 0.0): `paddle_client`
  (checkout transactions) + `paddle_webhook` (HMAC-SHA256 + 5 s
  replay window + `paddle_events` idempotency), `docs/PADDLE_SETUP.md`.
- CLI verified end-to-end: `vantia init` then `vantia status`.
- Engine bugs found by the tests and fixed (state_manager task
  indexing, logging frame access, end_run return value, quota RLock
  deadlock) — details in PLATFORM_STATE §10.
- Version-controlled: commits exist locally on `main` through the
  run-16 code commit `e9146e9`; push authorized by the user with the
  disclosed token (rotate at 100% per user), inline `oauth2:` URL only —
  never written to the repo.

## What's Left (24 tasks)
- Phase 5 (3): 5.4 SEO (reopened), 5.5 landing pages, 5.6 waitlist.
- Phase 6 (7): observability & deployment (status page, render.yaml,
  vercel.json, supabase guide, keep-alive docs).
- Phase 7 (3): acceptance (full E2E, failover, paid-model switching).
- Phase 8 (5): workspaces & multi-tenancy (auth, tables, RLS, storage) —
  run 17, in flight.
- Phase 13 (6): workspace UI + full journey.

## Current Milestone
Run 16 closed Phase 12 (6/6): **64/88 = 73%**, 540 tests / 94% coverage
(5177 stmts) / gates green / web build green. The continuous loop is on
**run 17 — Phase 8**, then 6 → 5 → 13 → 7 per `docs/BUILD_BOARD.md`.

## Blockers
- No Supabase / Render / Vercel / Paddle credentials (`REPLACE_ME`
  placeholders) — network-success verification deferred to launch prep.
- **GitHub token pasted in chat (session 11) is compromised — rotate
  it before the first push.** Never write tokens into the repository;
  pushes use an inline `oauth2:<token>@github.com/...` URL per
  `docs/RUNBOOK.md`.