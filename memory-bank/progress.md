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
- **Phase 5 complete (3/3, run 19 `9e9984e`):** 5.4 SEO, 5.5 landing pages, 5.6 waitlist.
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
- Suite (run 18, 2026-10-10): 61 test files / **597 passing** /
  **94% line coverage of `engine/`** (5412 stmts);
  `ruff check`, `ruff format --check` and `mypy` clean repo-wide;
  **web `next build` EXIT=0** (status page included).
- **Phase 6 complete (7/7, run 18 `bb0b130`):** observability & deploy —
  hash-pair structured logging on chain append; `web/app/status/page.tsx`;
  Dockerfile digest-pinned + pip==25.2 + non-root; `render.yaml` +
  `web/vercel.json` (`npm ci`); `RENDER_DEPLOY.md`, `VERCEL_DEPLOY.md`,
  `SUPABASE_SETUP.md` (0001→0005 rollout, parity-tested), `KEEP_ALIVE.md`;
  `tests/test_deploy_configs.py` cross-config/secret gate. All validated
  **structurally — nothing deployed or applied** (no credentials).
- **Phase 8 complete (5/5, run 17 `2b40f3c`):** user workspaces —
  offline HS256 JWT verification + refresh (PyJWT declared);
  `0004_workspaces.sql` (profiles/workspaces/files, cascade FKs, tier
  parity) + `0005_rls.sql` (12 `auth.uid()` policies, hardened
  `vantia_jwt_hook`) written + static-tested (**not applied** — no live
  Postgres); `WorkspaceService` ownership guard; `WorkspaceStorage`
  validate-before-network with honest codes; two-user isolation E2E.
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
- Version-controlled: commits exist on `main` through the run-18 code
  commit `bb0b130` (pushed continuously with the disclosed token under
  user authorization; user rotates it at 100% build).

## Phase 15 — EXTENSION (runs 21–22, all 16/16 complete, `d45d98a`)
- **15.1 job recommendations from CV** (`d5a3b8a`): `engine/ats/recommender.py` —
  six-signal weighted match (skill/experience/education/location/visa/recency),
  24h cache by sha256(cv_hash+filters), unparseable-CV fallback; `POST/GET
  /jobs/recommendations`; `web/app/jobs/recommended`.
- **15.2 direct application link verification**: `engine/sources/verify_links.py`
  — HTTPS-only, ATS allowlist, HEAD reachability, 6h freshness; `.github/workflows/verify-links.yml`.
- **15.3 anti-predatory enforcement**: `engine/security/predatory.py` —
  12 fee patterns, scam-aggregator list, PII-request + injection detectors;
  `ingest.rejected_jobs` audit with reason_code.
- **15.4 sponsor reliability scoring** (`5a8d276`): `engine/sources/sponsor_reliability.py`
  — 0–100 tenure/volume/consistency/volatility/user-signal; weekly cron.
- **15.5 CV-to-job spec mapping (Pro)** (`a2fd18e`): prompt `v1_cv_job_mapping.md`
  + schema + `engine/generators/cv_job_mapping.py`; tier-gated, 6,000 credits, debit-after-persist.
- **15.6 CV refinement chatbot**: `v1_chat_refine.md` + `engine/improve/chat_refine.py`
  — tier turn limits (free 3 / pro 20 / business ∞), 2,000/turn, `POST /improve/chat`.
- **15.7 mock interview generator (Pro)**: `v1_mock_interview.md` + schema; 10 questions, 4,000 credits.
- **15.8 application tracker** (`084d50f`): `engine/applications/tracker.py` — kanban
  (applied/interview/offer/rejected/withdrawn), job snapshot; `web/app/applications`.
- **15.9 job alert subscriptions** (`084d50f`): `engine/alerts/manager.py` + `send_digests.py`
  (Resend), `.github/workflows/job-alerts.yml` (daily 08:00 UTC); `web/app/alerts`.
- **15.10 scholarship calendar export** (`fc2dd7d`): `engine/scholarships/calendar.py`
  — RFC 5545 .ics; `/scholarships/{id}/ics` + `/scholarships/calendar.ics`.
- **15.11 referral program** (`b38fa98`): `engine/referrals/manager.py` — 8-char codes,
  5,000-credit both parties, idempotent; `web/app/referrals`.
- **15.12 public API** (`fdeebeb`): `engine/public_api/keys.py` — `vantia_sk_` SHA-256
  key auth, per-key rate limit; `/api/v1/ats/score` + equivalence; `docs/API.md`.
- **15.13 50-country coverage** (`2aa4f73`): `engine/sources/world.py` + `countries.py`
  — 54 countries (≥50), **JP the only Asian country, zero African countries** (per user).
- **15.14 real /status page** (`ce39b9f`): `/metrics` endpoint + rewritten `web/app/status`
  (data freshness / LLM providers / platform health / what's working).
- **15.15 eliminate all stubs** (`d45d98a`): pipeline page fully live (10 job steps + 7
  scholarship steps), all "launching soon" gone; `tests/test_stub_elimination.py`.
- **15.16 country tabs everywhere** (`d45d98a`): UK/DE/IE/SE/CA/AU/NZ/JP/All tabs on
  /jobs, /scholarships, /jobs/recommended, /pipeline; `?country=` shareable.

**RULE 0.3 conflict resolved (run 22):** pre-existing `test_web_pipeline.py::
test_pipeline_links_every_step_it_promises` asserted `"launching soon" in text`,
contradicting R29/Part 19.4 (`grep -r "launching soon" web/` = 0). Flipped that one
assertion to `not in` (kept the test + all other assertions; never removed it).

## What's Left (0 tasks)
- Phase 15 fully shipped (16/16). All 104 tasks complete. Suite green (828 passed),
  ruff+mypy green, web `next build` EXIT=0. main pushed to `origin/main` + `origin/vantia-state`.

## Current Milestone
Run 22: **104/104 tasks (100%)**. Phase 15 extension fully built, tested, and shipped.
Production: Vercel `vantia-rho.vercel.app`, Render `vantia-engine.onrender.com`,
Supabase (EU) `zpzzrlxkmnmposdnxpeg`, Paddle, 12-provider LLM failover.

## Blockers
- None. All credentials live (Supabase, Paddle, Render, Vercel). Golden path + 828 tests green.