# Changelog

All notable changes to Vantia are recorded here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/). Every engine task appends an
entry in the form `vantia(<task_id>): <name> (run N)`.

## [Unreleased]
### Google sign-in preflight — honest in-product failures (`/api/auth/google`)
- **Server preflight route** new `web/app/api/auth/google/route.ts`:
  the browser now starts Google sign-in at our own route, which asks
  GoTrue for the authorize redirect server-side (`redirect: "manual"`).
  A 302 is forwarded straight to the Google consent page; any refusal —
  provider disabled, redirect URL not allowlisted, missing env pair,
  Supabase unreachable — lands on `/auth/callback` with the *verbatim*
  reason plus the exact fix. A disabled provider can no longer dump a
  raw JSON 400 on `*.supabase.co` (favicon 404 included).
- `signInWithGoogle()` (`web/lib/engine.ts`) redirects to the preflight
  route; the Supabase authorize URL is now built server-side only.
- **Docs** `docs/AUTH.md` §1/§3 describe the preflight; the easiest
  verification is now `curl -sI …/api/auth/google` (302 to Google =
  flow starts; 302 to `/auth/callback?error=` = verbatim refusal).
- Gates: `tests/test_google_auth.py` updated (route preflight +
  refusal-pinning assertions); full suite + `next build` green.
- **Still blocked on the Supabase dashboard** (unchanged, config-only):
  the Google provider remains **disabled** on the live project
  (`authorize` → 400 `Unsupported provider: provider is not enabled`,
  re-verified 2026-10-13). Enable it under Authentication → Providers →
  Google and allow `…/auth/callback` under URL Configuration
  (`docs/AUTH.md` §3) — nothing in the repo can flip that toggle.

### Tools behind sign-in + two-track application pipeline (web)
- **Session gate** new `web/components/RequireSession.tsx` — the ATS
  scanner, CV improver, cover letter, credits dashboard and packs pages
  now render only for a signed-in account (Supabase session in
  localStorage); signed-out visitors get an honest "sign in first" card
  (Google button + email link to `/dashboard`). The tools load via
  `next/dynamic` with `ssr: false`, so the tool markup/bundle never
  reaches signed-out visitors — the public marketing copy stays
  (SEO surface unchanged, gated tool below it).
- **Credits purchase hardened** — `/credits/purchase` is gated and now
  buys packs against the verified session user id (JWT `sub`); the
  Phase-8 "type your user id" placeholder is gone.
- **Pipeline** new `/pipeline` page (noindex-free, sitemap-listed):
  two ordered, honestly-badged tracks — *If you are looking for a job*
  (account → baseline ATS → screened posting → posting ATS → ranked
  edits → cover letter → credits) and *If you are looking for a
  scholarship* (account → funded programmes → credential equivalence →
  academic CV → ranked edits → motivation letter → credits); every step
  links the page that performs it, launching-soon steps say so. Linked
  from the homepage, `/dashboard` (both tracks), `/jobs` and
  `/scholarships`.
- Gates: `tests/test_web_pipeline.py` (6), sitemap/title parity in
  `tests/test_web_seo.py` extended to seven pages; `next build` green.

### Google sign-in live diagnosis — provider disabled on the Supabase project (config, not code)
- **Root cause found (verified with `curl`, 2026-10-13)** — the live
  Supabase project answers `GET /auth/v1/authorize?provider=google`
  with HTTP 400 `Unsupported provider: provider is not enabled`; the
  browser lands on that JSON error page and its favicon request to
  `*.supabase.co` 404s (the console error seen next to the failure).
  Email/password auth, migration 0007 and engine CORS were each probed
  and are healthy; the `/admin` role gate is wired correctly.
- **Local dev fix** — git-ignored `web/.env.local` now carries the
  publishable `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  / `NEXT_PUBLIC_ENGINE_URL` trio (Next reads env from `web/`, not the
  repo root, so the buttons were disabled locally); docs note the
  port-3000 squatter (dev server starts on 3001) and the 3001 callback
  allowlist entry.
- **Docs** `docs/AUTH.md` §3 no longer claims the Google provider is
  "already done" on the live project — it records the verified status,
  the exact dashboard steps that remain, and a one-line curl check
  (302 = flow starts, 400 = still disabled).

### Google sign-in + role-gated `/admin`; waitlist CTA retired
- **Web auth** `signInWithGoogle()` + `/auth/callback` (noindex; handles
  implicit-hash and PKCE-`?code=` flows, saves the session, redirects to
  `/dashboard`); "Continue with Google" on the dashboard with
  email/password kept as fallback; identity still the verified JWT `sub`.
- **Admin bootstrap** `supabase/migrations/0007_admin_role.sql` —
  `profiles.role`; security-definer trigger promotes the **first
  Google** sign-in to `admin` (advisory-locked, google-provider only,
  backfilled for pre-migration logins); user-writable RLS policies
  refuse `role <> 'user'` so nobody self-promotes; anon revoked.
- **Admin gate** `web/app/admin/AdminGate.tsx` — `/admin` renders the
  console only for the signed-in `role=admin` account (role read with
  the user's own JWT under RLS); engine `VANTIA_ADMIN_TOKEN` stays the
  second factor; every failure state shown verbatim.
- **Waitlist CTA retired** — "Join the waitlist" removed from the
  homepage and all six landing pages, replaced by a "Sign in" →
  `/dashboard` CTA; `/waitlist` + confirm stay live for old links
  (double opt-in intact), just unlinked (static-enforced).
- **Docs** new `docs/AUTH.md`; `docs/ADMIN.md` §1 rewritten for the
  two-factor unlock.
- **Deploy fix** root `vercel.json` drops the FastAPI `app` service —
  its function bundle (303 MB) exceeds Vercel's 225 MB limit, which
  fails the whole root deploy; it also never served production traffic
  (`/api/*` answered 404; the engine runs on Render via
  `NEXT_PUBLIC_ENGINE_URL`). The web service is the only Vercel service.
- Gates: `tests/test_google_auth.py` (9), admin-gate test in
  `tests/test_admin_panel.py`, waitlist-retirement + CTA assertions in
  `tests/test_web_seo.py`; `next build` green.

### Admin panel — hidden `/admin` route (unbundled: no task id, deployment prep)
- **Engine** `engine/admin.py` + six token-gated routes in `engine/api.py`:
  `GET /admin/overview`, `PUT /admin/tiers`, `POST /admin/usage-tier`,
  `GET /admin/credits`, `POST /admin/credits/grant`, `POST /admin/users/tier`.
  Fail-closed auth (`VANTIA_ADMIN_TOKEN`; 503 `admin_not_configured` when unset,
  403 on mismatch); state writes take the run lock; env overrides are reported,
  never hidden; credits move through the append-only ledger (R46 stands).
- **Web** `web/app/admin/page.tsx` + `AdminConsole.tsx` — type the URL to open it:
  not linked anywhere, noindexed, absent from sitemap, `robots.txt` disallows it
  (`web/app/robots.ts`); runtime API-key entry (never a `NEXT_PUBLIC_*` var).
- **Render readiness** new `Render.com service environment` block in `.env` /
  `.env.example` with the ready-to-fill `VANTIA_ADMIN_TOKEN=` slot,
  `VANTIA_ADMIN_TOKEN` added to `render.yaml` (`sync: false`), the deploy-gate
  `SECRET_KEYS` set, and the `docs/RENDER_DEPLOY.md` env table.
- Gates: 18 admin API tests (`tests/test_admin_api.py`), 7 panel-surface tests
  (`tests/test_admin_panel.py`); full suite green; `next build` EXIT=0.

### Run 19 — Phase 5 (5.4–5.6): SEO, landing pages & waitlist double opt-in
- **5.4** Layout metadata, JSON-LD, and honest sitemap.
- **5.5** Six SEO landing pages with metadata and JSON-LD.
- **5.6** Waitlist double opt-in flow (API routes, Supabase table, outbox sender).


### Run 18 — Phase 6 (6.1–6.7): Observability & Deployment
- **6.1** `hash_chain.append` now emits structured JSON log lines with
  `run_id` + `seq`/`sha256`/`prev_hash` — stdout is auditable even when
  the chain file is out of reach (test parses the real stdout line).
- **6.2** `web/app/status/page.tsx` public status page (live `GET /status`
  data, honest unreachable state, 30 s refresh); `next build` EXIT=0.
- **6.3** Dockerfile reproducibility: base digest-pinned
  (`python:3.12-slim@sha256:a6e34c59…`, resolved via Docker Hub API),
  pip==25.2 + `pip check`, non-root `USER vantia`.
- **6.4** `render.yaml` Blueprint (Docker, `/health`, `autoDeploy: false`,
  secrets `sync: false`) + `docs/RENDER_DEPLOY.md` (**NOT DEPLOYED**).
- **6.5** `web/vercel.json` (`npm ci` from the committed lockfile) +
  `docs/VERCEL_DEPLOY.md` incl. the CORS contract (**NOT DEPLOYED**).
- **6.6** `docs/SUPABASE_SETUP.md` — 0001→0005 rollout in order
  (parity-tested), post-apply verification SQL, dashboard steps
  (**NOT APPLIED**).
- **6.7** `docs/KEEP_ALIVE.md` — three layers, verification, pre-deploy
  red-state rule, failure matrix; cron parity-tested (`*/14`).
- Gate: `tests/test_deploy_configs.py` (14 tests) — cross-config parity,
  secret scans (`ghp_`/`REPLACE_ME`), required NOT-DEPLOYED headers.
- Defects found: the four promised Phase-6 runbooks never existed;
  Dockerfile base unpinned + root user; logging lacked hash fields.
- 61 files / 597 tests / 94% (5412 stmts); web build green.

### Run 17 — Phase 8 (8.1–8.5): User Workspaces
- **8.1** `engine/auth/` — offline HS256 Supabase JWT verification
  (algorithm pinned, `sub`+`exp` required, placeholder secret refuses
  loudly) + coded refresh flow; `AuthError` taxonomy; PyJWT declared in
  requirements/pyproject (was importable but undeclared).
- **8.2** `0004_workspaces.sql` — profiles / workspaces / workspace_files
  with cascade FKs and a tier CHECK parity-tested against the engine's
  `TIERS`; `WorkspaceService` (idempotent profile, ownership guard,
  loud `workspace_backend_unconfigured`); `SupabaseClient.delete()`.
- **8.3** `0005_rls.sql` — RLS on all three tables, 12 policies scoped to
  `auth.uid()` (files via parent ownership), no `using (true)`, hardened
  `vantia_jwt_hook` that stamps the profile tier (dashboard registration
  is a documented launch step).
- **8.4** `WorkspaceStorage` — user-scoped object paths, traversal-proof
  segments, size/extension validation before any HTTP, honest
  `storage_unconfigured` / `workspace_file_missing` / `workspace_forbidden`.
- **8.5** offline two-user isolation E2E: cross-user access refused
  before **zero** storage calls; expired tokens stop everything;
  traversal never reaches HTTP; touched-host pin.
- Migrations 0004/0005 written + static-tested, **not applied** (no live
  Postgres — recorded honestly).
- 60 files / 583 tests / 94% (5409 stmts); auth 98%, storage 95%.

### Run 16 — Phase 12 (12.1–12.6): Credit Purchasing
- **12.1** `docs/PADDLE_SETUP.md` audited against the code: phantom
  `/api/*` route paths corrected to the real `POST /credits/checkout` /
  `POST /paddle/webhook`; dashboard-level return URLs documented (SDK
  surface verified); verify section gains the new test files + web build
  gate. `.env.example`: `NEXT_PUBLIC_ENGINE_URL`, `VANTIA_ALLOWED_ORIGINS`.
- **12.2** `POST /credits/checkout` — stable 422 codes, honest **502**
  when Paddle keys are unset (never a fake URL); dead `success_url`/
  `cancel_url` client params removed after verifying the installed SDK;
  `custom_data` attribution pinned by test.
- **12.3** `POST /paddle/webhook` route (raw body + signature header,
  400 on bad signature) over the existing audit-verified handler.
- **12.4** exactly-once top-ups via layered idempotency +
  `0003_paddle.sql` — the `paddle_events` table the docs promised but
  that had never been created (static-tested against the handler).
- **12.5** `GET /credits/packs` UI data; `web/app/credits/purchase/page.tsx`
  purchase page; engine CORS (`VANTIA_ALLOWED_ORIGINS`, never `*`).
  **First web build gate:** found + fixed the pre-existing sitemap
  `dynamic`/`cacheComponents` conflict; `next build` EXIT=0.
- **12.6** offline purchase E2E: packs → checkout → webhook credits once →
  redelivery no-op → payment_failed records only → forged signature 400.
- Drift closed: `.env.example` `VANTIA_*_TIER_TOKENS` vars are now real
  env overlays in `load_credits_config` (loud on invalid values).
- 55 files / 540 tests / 94% (5177 stmts); ruff + format + mypy green.

### Run 15 — Phase 11 (11.1–11.6): Credit System
- **11.1** `engine/credits/ledger.py` — local-first append-only credit
  ledger: signed movements with `balance_after` + caller `ref`, idempotent
  by `(user_id, ref)`, R46 `InsufficientCredits` writes nothing, best-effort
  Supabase mirror; `supabase/migrations/0002_credits.sql` balance/ledger
  tables (static-tested with engine↔SQL kind parity). Corrupt store fails
  loudly (`ledger_corrupt`) instead of resetting balances.
- **11.2** `engine/credits/metering.py` — `operation_cost()` priced from
  state `token_costs` (unknown operation never runs free); `CreditMeter`
  pre-flights before work and charges on completion only.
- **11.3** `engine/credits/tiers.py` — free/pro/business read from state;
  recorded-not-inferred tiers; allowance granted exactly once per month
  (idempotent ref); read-only `projected_balance()`.
- **11.4** pipelines 9.5/10.2/10.4 accept `user_id`: pre-flight (allowance
  + R46) before any I/O, charge only after schema-valid persistence,
  `credits` reported in the result; no `user_id` → unchanged behavior.
- **11.5** `GET /credits/balance` (one dashboard payload) +
  `GET /credits/estimate` (read-only, stable 422 codes).
- **11.6** offline E2E credit journey: allowance → metered runs → R46
  refusal with **zero network calls** → webhook double-delivery credits
  once → shortfall estimate → full entry history.
- Stale `ledger_pending` webhook stub test replaced with wired behavior.
- 52 files / 516 tests / 93% (5120 stmts); ledger 98%, tiers 97%,
  metering 100%; ruff + format + mypy green.

### Run 14 — Phase 10 (10.1–10.6): CV improvement + cover letter
- Reconciliation: the build board and `PLATFORM_STATE.md` both lagged the
  working tree — all six Phase 10 tasks already existed; the suite was run
  (462 green, 93% cov) before anything was recorded.
- **10.1 / 10.3** recorded (audit-verified): `v1_cv_improve.md` +
  `cv_improvement.schema.json`, `v1_cover_letter.md` +
  `cover_letter.schema.json` (already tested in `test_prompts`/`test_schemas`).
- **10.2** `engine/improve/cv.py` — deterministic fact-preserving CV edits
  (canonical rebuild, honest placeholders, keyword mirroring only for
  evidenced skills, sanctioned verb/filler swaps), ≤30 ranked improvements,
  recomputed summaries; `run_cv_improvement` wired (store resolution +
  traversal guard + `<file>.improve.json`).
- **10.4** `engine/generators/cover.py` — facts-only cover letters (real
  title/employer, ≤2 verbatim quantified bullets, resume's own keyword
  spelling, Achievement dropped rather than faked); `run_cover_letter` wired
  (robots/rate-limit/closed-refusal, `<file>.cover.json`).
- **10.5 / 10.6** offline E2E flows for both pipelines.
- 47 files / 462 tests / 93% (4807 stmts); new modules 92–96%; gates green.

### Run 13 — Phase 9 (9.1–9.6): ATS scoring engine
- **9.1** Resume parser (PDF/DOCX/TXT/MD/JSON) with honest extraction
  confidence and loud extractor failures — repaired 3 latent bugs (unbound
  `_strings` on profiles without `languages`, MIME-tail format hints always
  falling back to `txt`, missing-extra errors escaping unwrapped).
- **9.2** Twelve-point scoring rubric (`CATEGORY_WEIGHTS` = 100): deterministic,
  demand-detected categories, dated-facts-only experience, a suggestion for
  every sub-100 category; schema-valid payload on every path.
- **9.3** Keyword matcher + gap analysis (exact/stem/synonym) — stemmer plural
  rule fixed so `databases` matches `database`.
- **9.4** `POST /ats/score` (422 stable codes vs 500 for our own payload bugs)
  + `GET /status` state summary.
- **9.5** `run_ats_scan`: store resolution with traversal guard, parse-before-
  network, robots/rate-limit/closed-refusal, report persisted as
  `<file>.ats.json`.
- **9.6** `tests/e2e/test_ats_journey.py` — offline journey, touched-host pin,
  robots refusal, API-scores-stored-upload.
- Tooling: `state.start_run()` annotation corrected, `domain.py` dnspython
  typing fixed, repo-wide ruff/format/mypy green. 42 files / 436 tests / 93%.

### Session 11 — audit & reconciliation (no run)
- **Drift repaired:** `PLATFORM_STATE.md` §3 rows for Phases 2–5 restored from
  HEAD (a local edit had reverted them to ⏳ and deleted §10 sessions);
  manifest run-12 backfill; memory-bank + this changelog brought current.
- **5.1 / 5.2 recorded** (commit `9775b07` — full CLI surface, was unrecorded);
  **5.3 recorded** (commit `1efcae1` — `web/` Next.js skeleton adopted).
- **5.4 reopened** — claimed complete but only the sitemap route exists
  (no schema.org/JSON-LD, stock metadata); lands in run 19.
- **`engine/ats/` audit:** 9.1/9.3 written but untested; 9.2 `scoring.py`
  had a fatal SyntaxError — repaired with tests in run 13.

### Run 12 — Phase 4 (4.1–4.5)
- **4.1** Domain verification (DNS A/CNAME, provider expectation table, injectable resolver).
- **4.2** Tamper-evident idempotency registry (`entry_hash`, `verify()`).
- **4.3** Cross-run SHA-256 hash chain (`audit()`, `record_run()`).
- **4.4** Incident reporter — GitHub issue via `gh` + offline Markdown draft fallback.
- **4.5** Supabase schema migration `supabase/migrations/0001_init.sql` (static-tested).

### Run 11 — Phase 3 closeout (3.2, 3.3, 3.6, 3.7)
- **3.2** SOP generator, **3.3** research proposal generator (deterministic-first,
  schema-valid, optional LLM polish via shipped prompts).
- **3.6** `run_scholarship_pipeline` wired end to end; **3.7** offline E2E (7 journeys).

### Run 10 — Phase 3 data layer (3.1, 3.4, 3.5)
- **3.1** Scholarship database (5 sourced programs); **3.4** academic credential
  mapper (three-valued verdict); **3.5** application window tracker.

### Run 9 — Phase 2 closeout (2.4, 2.8, 2.9)
- **2.4** Credential equivalence lookup (28-row sourced registry, GPA→ECTS).
- **2.8** `run_job_pipeline` wired (fetch → screens → badge → ATS resume).
- **2.9** Offline E2E job pipeline (8 journeys, touched-host pin).

### Run 8 — Security guardrails + resume generator (2.5, 2.6, 2.7)
- **2.5** Fraud filter (domain/fee/middleman); **2.6** injection + PII redactor;
  **2.7** ATS resume generator.

### Run 7 — 2.3 follow-up: all-country register coverage
- RegisterSpec dispatch over all 50 European countries + AU; generic
  page→CSV pipeline; unknown-code rejection.

### Run 6 — Registers, gov jobs, Europe DB (2.3)
- Sponsor registers UK/AU/DE, German gov jobs API, 50-country Europe DB,
  active-only + sponsorship-tag policy.

### Run 5 — Portal adapters (2.2)
- Workday / Greenhouse / Lever adapters on the shared fetcher.

### Run 4 — Fetch base (2.1)
- `engine/sources/`: robots.txt gate, per-domain rate limit, backoff, size cap.

### Run 3 — Phase 1 closeout (1.1–1.4)
- Envelope + ATS/SOP/research-proposal schemas; prompt templates v1 (5 templates,
  security blocks + honesty guards).

### Run 2 — Phase 1 LLM stack (1.5–1.7) + task 0.0
- **1.5** `providers.yaml` (22 providers: 12 free / 10 paid); **1.6** free-first
  failover router + quota tracker; **1.7** LLM client (dry-run, cost ceiling,
  hash-chained envelopes) + `json_utils` fence stripper.
- **0.0** Stripe → Paddle migration (`paddle_client`, `paddle_webhook`,
  `docs/PADDLE_SETUP.md`; every `STRIPE_*` reference removed).

### Run 1 — Phase 0 (Scaffold)
- **0.1** Init repo structure — full §3 tree, `bootstrap.sh`, packaging,
  Dockerfile, requirements.
- **0.2** Create `vantia-state` orphan branch (authoritative state + artifacts).
- **0.3** Write state seed (`state.json`, 98 tasks) + `state_manager`.
- **0.4** Add GitHub Actions workflows (`vantia.yml`, `keep-alive.yml`, `ci.yml`).
- **0.5** Idempotency registry + cross-run SHA-256 hash chain + state locking.
- **0.6** Structured logging + cost tracker + error taxonomy.
- **0.7** Supabase integration (persistence client + git fallback).
- **0.8** FastAPI `/health` + self-ping keep-alive thread.
- **0.9** Keep-alive GitHub Actions workflow.

## [0.4.0] — Master prompt v4.0
- Adds user workspaces, ATS scoring, AI CV improvement, cover letters,
  credit system, credit purchasing, and usage-tier enforcement.
