# Changelog

All notable changes to Vantia are recorded here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/). Every engine task appends an
entry in the form `vantia(<task_id>): <name> (run N)`.

## [Unreleased]

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
