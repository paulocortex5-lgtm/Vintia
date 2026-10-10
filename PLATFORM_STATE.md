# VANTIA — PLATFORM STATE

**Last updated:** 2026-10-10T11:36:37Z
**Master prompt:** v6.0
**Session count:** 12
**Overall readiness:** 73%

---

## 1. SHIPPING READINESS SUMMARY

| Metric | Value |
|---|---|
| Tasks complete | 64/88 |
| Tasks in progress | 0 |
| Tasks blocked | 0 |
| Tasks pending | 24 |
| Audit failures | 1 (5.4 — reopened in session 11) |
| Live previews passing | 0 |
| E2E tests passing | 27 (7 offline suites) |
| Backend deployed | no |
| Frontend deployed | no |
| Database migrated | no |
| Auth working | no |
| Payments working | no |
| **Ready to ship?** | **NO** |

---

## 2. PHASE-BY-PHASE PROGRESS

| Phase | Name | Complete | In Progress | Blocked | Pending | % |
|---|---|---|---|---|---|---|
| 0 | Scaffold | 9/9 | 0 | 0 | 0 | 100% |
| 1 | Schemas + Prompts + LLM Router | 7/7 | 0 | 0 | 0 | 100% |
| 2 | Jobs Trail | 9/9 | 0 | 0 | 0 | 100% |
| 3 | Scholarship Engine | 7/7 | 0 | 0 | 0 | 100% |
| 4 | Verification & Hardening | 5/5 | 0 | 0 | 0 | 100% |
| 5 | Product Surface | 3/6 | 0 | 0 | 3 | 50% |
| 6 | Observability & Deployment | 0/7 | 0 | 0 | 7 | 0% |
| 7 | Acceptance | 0/3 | 0 | 0 | 3 | 0% |
| 8 | User Workspaces | 0/5 | 0 | 0 | 5 | 0% |
| 9 | ATS Scoring Engine | 6/6 | 0 | 0 | 0 | 100% |
| 10 | CV Improvement + Cover Letter | 6/6 | 0 | 0 | 0 | 100% |
| 11 | Credit System | 6/6 | 0 | 0 | 0 | 100% |
| 12 | Credit Purchasing | 6/6 | 0 | 0 | 0 | 100% |
| 13 | Workspace UI + Full Journey | 0/6 | 0 | 0 | 6 | 0% |

---

## 3. TASK-BY-TASK STATUS

### Phase 0 — Scaffold

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 0.1 | Init repo structure | ✅ Complete | 4c84504 | pyproject.toml, requirements.txt, requirements-dev.txt, .gitignore, .gitattributes, .dockerignore, .env.example, README.md, LICENSE, CHANGELOG.md, Dockerfile, bootstrap.sh | ❌ | ❌ | ✅ |
| 0.2 | Create vantia-state orphan branch | ✅ Complete | aa0f228 | .vantia/state/state.json, .vantia/artifacts/.gitkeep, .vantia/run_manifest.json, .vantia/README.md | ❌ | ❌ | ✅ |
| 0.3 | Write state seed + state_manager | ✅ Complete | 4c84504 | engine/seed/state.json, engine/state_manager.py, engine/locking.py | ❌ | ❌ | ✅ |
| 0.4 | Add GitHub Actions workflows | ✅ Complete | 4c84504 | .github/workflows/vantia.yml, .github/workflows/ci.yml, .github/workflows/keep-alive.yml, docs/RUNBOOK.md | ❌ | ❌ | ✅ |
| 0.5 | Idempotency + hash chain + locking | ✅ Complete | 4c84504 | engine/idempotency.py, engine/hash_chain.py | ❌ | ❌ | ✅ |
| 0.6 | Logging + cost tracker + errors | ✅ Complete | 4c84504 | engine/logging_config.py, engine/cost_tracker.py, engine/errors.py, engine/retry.py | ❌ | ❌ | ✅ |
| 0.7 | Supabase integration | ✅ Complete | 4c84504 | engine/persistence/supabase_client.py, engine/persistence/fallback.py | ❌ | ❌ | ✅ |
| 0.8 | FastAPI /health + self-ping keep-alive | ✅ Complete | 4c84504 | engine/api.py, engine/keep_alive.py | ❌ | ❌ | ✅ |
| 0.9 | Keep-alive GitHub Actions workflow | ✅ Complete | 4c84504 | .github/workflows/keep-alive.yml | ❌ | ❌ | ✅ |

### Phase 1 — Schemas + Prompts + LLM Router

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 1.1 | Envelope + ATS schema | ✅ Complete | `001b78e` | engine/schemas/envelope.schema.json (in sync with `ENVELOPE_FIELDS`, 17 keys), engine/schemas/ats_score.schema.json, engine/llm/client.py, tests/test_schemas.py, tests/test_llm_client.py | ✅ | ❌ | ✅ |
| 1.2 | SOP schema | ✅ Complete | `001b78e` | engine/schemas/sop.schema.json, tests/test_schemas.py | ✅ | ❌ | ✅ |
| 1.3 | Research proposal schema | ✅ Complete | `001b78e` | engine/schemas/research_proposal.schema.json, tests/test_schemas.py | ✅ | ❌ | ✅ |
| 1.4 | Prompt templates v1 | ✅ Complete | `001b78e` | engine/prompts/v1_ats_score.md, engine/prompts/v1_sop.md, engine/prompts/v1_research_proposal.md (plus pre-existing v1_cv_improve.md / v1_cover_letter.md), tests/test_prompts.py | ✅ | ❌ | ✅ |
| 1.5 | LLM provider registry (providers.yaml) | ✅ Complete | `279c3ca` | engine/llm/providers.yaml (22 providers: 12 free / 10 paid), engine/llm/router.py, engine/llm/__init__.py, tests/test_llm_router.py | ✅ | ❌ | ✅ |
| 1.6 | LLM router + multi-provider failover | ✅ Complete | `279c3ca` | engine/llm/quota.py, tests/test_quota.py | ✅ | ❌ | ✅ |
| 1.7 | LLM client + fence stripper + quota | ✅ Complete | `279c3ca` | engine/llm/client.py, engine/json_utils.py, engine/llm/__init__.py, tests/test_llm_client.py, tests/test_json_utils.py | ✅ | ❌ | ✅ |

### Phase 2 — Jobs Trail

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 2.1 | Fetch base + robots.txt + rate limit | ✅ Complete | `902c115` | engine/sources/fetch.py, engine/sources/robots.py, engine/sources/ratelimit.py, engine/sources/__init__.py, engine/errors.py (TransientFetchError), tests/test_sources.py, .env.example, bootstrap.sh | ✅ | ❌ | ✅ |
| 2.2 | Portal adapters (W/G/L) | ✅ Complete | `8dbcdec` | engine/sources/portals/ (base + greenhouse + lever + workday + registry), Fetcher.post() in engine/sources/fetch.py, tests/test_portals.py, tests/test_sources.py | ✅ | ❌ | ✅ |
| 2.3 | Visa register fetchers (UK/DE/AU) | ✅ Complete | `2272dc7` | engine/sources/registers.py, engine/sources/government.py, engine/sources/countries.py (+gov listing fields, active-only, sponsorship tagging), tests/test_registers.py, tests/test_government.py, tests/test_countries.py, docs/SOURCES.md | ✅ | ❌ | ✅ |
| 2.4 | Credential equivalence lookup | ✅ Complete | `bb8d7e3` | engine/credentials/__init__.py, engine/credentials/equivalence.py (28-row registry, lookup/describe/equivalence, GPA→ECTS, owner-configured remote_lookup on Fetcher), tests/test_credentials.py | ✅ | ❌ | ✅ |
| 2.5 | Fraud filter (domain/fee/middleman) | ✅ Complete | `1e40b27` | engine/security/fraud.py, engine/security/__init__.py, tests/test_security.py (fraud section) | ✅ | ❌ | ✅ |
| 2.6 | Injection + PII redactor | ✅ Complete | `1e40b27` | engine/security/injection.py, engine/security/redact.py, tests/test_security.py (injection/redact sections) | ✅ | ❌ | ✅ |
| 2.7 | ATS resume generator | ✅ Complete | `1e40b27` | engine/generators/resume.py, engine/generators/__init__.py, tests/test_resume.py | ✅ | ❌ | ✅ |
| 2.8 | pipeline.py: run_job_pipeline | ✅ Complete | `bb8d7e3` | engine/pipeline.py (fetch → active screen → fraud screen → register badge → load_profile → generate_resume), engine/generators/profile.py, tests/test_pipeline.py | ✅ | ❌ | ✅ |
| 2.9 | E2E job pipeline test | ✅ Complete | `bb8d7e3` | tests/e2e/test_job_pipeline.py (8 journeys on httpx.MockTransport, touched-host pin) | ✅ | ❌ | ✅ |

### Phase 3 — Scholarship Engine

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 3.1 | Scholarship database (5 programs) | ✅ Complete | `f299b00` | engine/scholarships/database.py (5 sourced rows, verified URLs, get/search), tests/test_scholarships.py | ✅ | ❌ | ✅ |
| 3.2 | SOP generator | ✅ Complete | `3821a8e` | engine/generators/sop.py (5 sections, schema-valid, honest placeholders, v1_sop polish), tests/test_sop.py | ✅ | ❌ | ✅ |
| 3.3 | Research proposal generator | ✅ Complete | `3821a8e` | engine/generators/proposal.py (question/abstract/timeline, refuses fake keywords, v1_research_proposal polish), tests/test_proposal.py | ✅ | ❌ | ✅ |
| 3.4 | Academic credential mapper | ✅ Complete | `f299b00` | engine/scholarships/mapper.py (three-valued verdict vs min_eqf_level), tests/test_scholarships.py | ✅ | ❌ | ✅ |
| 3.5 | Application window tracker | ✅ Complete | `f299b00` | engine/scholarships/windows.py (month/day precision, wrap cycles, unknown state), tests/test_scholarships.py | ✅ | ❌ | ✅ |
| 3.6 | pipeline.py: run_scholarship_pipeline | ✅ Complete | `3821a8e` | engine/pipeline.py (db → profile → credential map → window → SOP + proposal), tests/test_pipeline.py | ✅ | ❌ | ✅ |
| 3.7 | E2E scholarship pipeline test | ✅ Complete | `3821a8e` | tests/e2e/test_scholarship_pipeline.py (7 journeys, network pinned dead, schemas validated) | ✅ | ❌ | ✅ |

### Phase 4 — Verification & Hardening

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 4.1 | Domain verification (DNS + CNAME) | ✅ Complete | `b6a5cad` | engine/verification/domain.py (A/CNAME checks, provider expectation table, injectable resolver, loud degradation without dnspython), tests/test_domain_verification.py | ✅ | ❌ | ❌ |
| 4.2 | Idempotency registry persistence | ✅ Complete | `b6a5cad` | engine/idempotency.py (entry_hash per entry, verify() tamper check, entries()), tests/test_idempotency.py | ✅ | ❌ | ❌ |
| 4.3 | Cross-run SHA-256 hash chain | ✅ Complete | `b6a5cad` | engine/hash_chain.py (audit() + record_run()), tests/test_hash_chain.py | ✅ | ❌ | ❌ |
| 4.4 | Circuit breaker + GitHub issue | ✅ Complete | `b6a5cad` | engine/incidents.py (gh CLI issue + offline draft fallback), execute_step wiring, tests/test_incidents.py | ✅ | ❌ | ❌ |
| 4.5 | Supabase schema migration + RLS | ✅ Complete | `b6a5cad` | supabase/migrations/0001_init.sql (mirror tables, CHECK-constrained statuses, JSONB, task_progress view), tests/test_sql_schema.py | ✅ | ❌ | ❌ |

### Phase 5 — Product Surface

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 5.1 | CLI: apply/status/resume/verify/reset | ✅ Complete | `9775b07` | engine/cli.py (init/apply/status/resume/verify/reset, dependency-aware apply, block handling), tests/test_cli.py, tests/cli_runners.py | ✅ | ❌ | ✅ |
| 5.2 | Golden-file CLI tests | ✅ Complete | `9775b07` | tests/test_cli.py (init idempotency, status after init, apply completes task + appends chain, failure→retry→block, reset), tests/cli_runners.py | ✅ | ❌ | ✅ |
| 5.3 | Web UI skeleton (Next.js) | ✅ Complete | `1efcae1` | web/ (Next.js app router: layout, page, globals.css, next.config.ts, tsconfig, static sitemap route, lib/settings.ts baseUrl) | ✅ | ❌ | ✅ |
| 5.4 | SEO: schema.org + sitemap | ⏳ Pending | — | audit (s11): sitemap route exists, but **no schema.org/JSON-LD** and metadata still "Create Next App" — reopened, lands in run 19 | ❌ | ❌ | ❌ |
| 5.5 | SEO landing pages (6) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 5.6 | Waitlist + double opt-in | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

### Phase 6 — Observability & Deployment

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 6.1 | Structured logging (run_id, hashes) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 6.2 | Public status page | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 6.3 | Docker + reproducibility | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 6.4 | Render deployment config (render.yaml) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 6.5 | Vercel deployment config | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 6.6 | Supabase setup guide + SQL migration | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 6.7 | Keep-alive documentation | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

### Phase 7 — Acceptance

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 7.1 | Acceptance demo (full E2E) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 7.2 | Multi-provider failover E2E test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 7.3 | Paid model switching E2E test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

### Phase 8 — User Workspaces

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 8.1 | Supabase Auth integration | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 8.2 | User profile + workspace tables | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 8.3 | Workspace RLS policies + JWT hook | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 8.4 | Private file storage (Supabase Storage) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 8.5 | Workspace isolation E2E test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

### Phase 9 — ATS Scoring Engine

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 9.1 | Resume parser (PDF/DOCX extraction) | ✅ Complete | `ba616fa` | engine/ats/parser.py (PDF/DOCX/TXT/MD/JSON, format detection incl. MIME hints, loud `resume_extractor_unavailable`/`resume_parse_error`, honest `extraction_confidence`), tests/test_ats_parser.py | ✅ | ❌ | ✅ |
| 9.2 | ATS scoring engine (12-point) | ✅ Complete | `ba616fa` | engine/ats/scoring.py (CATEGORY_WEIGHTS = 100, deterministic rubric, demand detection, suggestion per sub-100 category), tests/test_ats_scoring.py | ✅ | ❌ | ✅ |
| 9.3 | Keyword matcher + gap analysis | ✅ Complete | `ba616fa` | engine/ats/keywords.py (job/resume keywords, exact/stem/synonym match, coverage, honest gap report; stemmer plural fix), tests/test_ats_keywords.py | ✅ | ❌ | ✅ |
| 9.4 | ATS score schema + API | ✅ Complete | `ba616fa` | engine/api.py (`POST /ats/score` schema-valid on every path, 422 vs 500 split; `GET /status`), tests/test_ats_api.py | ✅ | ❌ | ✅ |
| 9.5 | ATS scan pipeline integration | ✅ Complete | `ba616fa` | engine/pipeline.py (`run_ats_scan`: store resolution → parse-before-network → traversal guard → listing load → score → schema validate → persist `<file>.ats.json`), tests/test_ats_scan.py | ✅ | ❌ | ✅ |
| 9.6 | ATS scan E2E test | ✅ Complete | `ba616fa` | tests/e2e/test_ats_journey.py (offline journey on MockTransport, touched-host pin, robots refusal, API scores a stored upload) | ✅ | ❌ | ✅ |

### Phase 10 — CV Improvement + Cover Letter

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 10.1 | CV improvement prompt + schema | ✅ Complete | `1003b3e` | engine/prompts/v1_cv_improve.md, engine/schemas/cv_improvement.schema.json (tested in tests/test_prompts.py, tests/test_schemas.py) | ✅ | ❌ | ✅ |
| 10.2 | CV improver engine | ✅ Complete | `1003b3e` | engine/improve/cv.py (deterministic fact-preserving edits, ≤30 ranked, schema-valid polish), engine/pipeline.py (`run_cv_improvement`), tests/test_improve.py | ✅ | ❌ | ✅ |
| 10.3 | Cover letter prompt + schema | ✅ Complete | `1003b3e` | engine/prompts/v1_cover_letter.md, engine/schemas/cover_letter.schema.json (tested in tests/test_prompts.py, tests/test_schemas.py) | ✅ | ❌ | ✅ |
| 10.4 | Cover letter generator | ✅ Complete | `1003b3e` | engine/generators/cover.py (facts-only letter), engine/pipeline.py (`run_cover_letter`), tests/test_cover_letter.py | ✅ | ❌ | ✅ |
| 10.5 | CV improvement E2E test | ✅ Complete | `1003b3e` | tests/e2e/test_cv_improvement_flow.py (offline flow, traversal guard, schema-valid) | ✅ | ❌ | ✅ |
| 10.6 | Cover letter E2E test | ✅ Complete | `1003b3e` | tests/e2e/test_cover_letter_flow.py (offline flow) | ✅ | ❌ | ✅ |

### Phase 11 — Credit System

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 11.1 | Credit ledger + balance tables | ✅ Complete | `c1591d1` | engine/credits/ledger.py (append-only, idempotent by ref, R46, STEP-K mirror), engine/credits/config.py, supabase/migrations/0002_credits.sql, tests/test_ledger.py, tests/test_credits_sql.py | ✅ | ❌ | ✅ |
| 11.2 | Token metering middleware | ✅ Complete | `c1591d1` | engine/credits/metering.py (operation_cost from state token_costs, CreditMeter pre-flight/charge/metered), tests/test_metering.py | ✅ | ❌ | ✅ |
| 11.3 | Tier definitions + enforcement | ✅ Complete | `c1591d1` | engine/credits/tiers.py (free/pro/business from state, once-per-month idempotent allowance, R46 enforce, projected read), tests/test_metering.py | ✅ | ❌ | ✅ |
| 11.4 | Credit deduction on task completion | ✅ Complete | `c1591d1` | engine/pipeline.py (`_begin_charge`/`_end_charge` on 9.5/10.2/10.4 — pre-flight before work, charge only on success, `credits` in result), tests/e2e/test_credit_journey.py | ✅ | ❌ | ✅ |
| 11.5 | Credit balance API + UI data | ✅ Complete | `c1591d1` | engine/api.py (`GET /credits/balance` one-payload dashboard data, `GET /credits/estimate` read-only with projected allowance), tests/test_credits_api.py | ✅ | ❌ | ✅ |
| 11.6 | Credit system E2E test | ✅ Complete | `c1591d1` | tests/e2e/test_credit_journey.py (offline journey: allowance → metered runs → R46 refusal before network → webhook double-delivery → estimate shortfall), tests/test_paddle_webhook.py (stub updated to wired behavior) | ✅ | ❌ | ✅ |

### Phase 12 — Credit Purchasing

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 12.1 | Paddle account + product setup | ✅ Complete | `e9146e9` | docs/PADDLE_SETUP.md (route paths corrected to `POST /credits/checkout` + `POST /paddle/webhook`, dashboard return URLs documented, 0002/0003 migrations + CORS + verify gates), .env.example (full Paddle + NEXT_PUBLIC_ENGINE_URL + VANTIA_ALLOWED_ORIGINS) | ✅ | ❌ | ✅ |
| 12.2 | Paddle Checkout endpoint | ✅ Complete | `e9146e9` | engine/api.py (`POST /credits/checkout` — stable 422 `user_id_required`/`unknown_pack`, honest 502 `paddle_error`), engine/credits/paddle_client.py (dead success/cancel params removed after verifying the installed SDK), tests/test_paddle_api.py | ✅ | ❌ | ✅ |
| 12.3 | Paddle webhook handler | ✅ Complete | `e9146e9` | engine/api.py (`POST /paddle/webhook` raw-body route, 400 on bad signature) + engine/credits/paddle_webhook.py (existing, credited since run 15), tests/test_paddle_api.py, tests/test_paddle_webhook.py | ✅ | ❌ | ✅ |
| 12.4 | Credit top-up logic + idempotency | ✅ Complete | `e9146e9` | exactly-once by layered idempotency (event_id row + ledger ref `paddle:<event>`); supabase/migrations/0003_paddle.sql (paddle_events table the doc promised but never existed), tests/test_paddle_sql.py | ✅ | ❌ | ✅ |
| 12.5 | Credit purchase UI | ✅ Complete | `e9146e9` | engine/api.py (`GET /credits/packs` UI data), web/app/credits/purchase/page.tsx (packs + honest errors + localStorage user id until Phase 8 auth), engine CORS (`VANTIA_ALLOWED_ORIGINS`, never `*`); **web build gate verified**: `next build` EXIT=0 — found + fixed pre-existing sitemap `dynamic`/`cacheComponents` conflict | ✅ | ✅ | ✅ |
| 12.6 | Paddle webhook E2E test | ✅ Complete | `e9146e9` | tests/e2e/test_paddle_purchase_flow.py (offline: packs → checkout → webhook credits once → redelivery no-op → payment_failed records only → forged signature 400 → balance/estimate reflect top-up) | ✅ | ❌ | ✅ |

### Phase 13 — Workspace UI + Full Journey

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 13.1 | Workspace dashboard UI | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 13.2 | ATS scan UI (upload + score view) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 13.3 | CV improvement UI | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 13.4 | Cover letter UI | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 13.5 | Credits dashboard UI | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 13.6 | Full user journey E2E test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

**Status legend:** ⏳ Pending · 🔄 In Progress · ✅ Complete · ⛔ Blocked · ⚠️ Audit Failure

---

## 4. FEATURE-LEVEL READINESS (from user's point of view)

| User-facing feature | Backend | Frontend | Auth | Tested | Previewed | Ready? |
|---|---|---|---|---|---|---|
| Sign up / sign in | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Upload CV to workspace | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Scan CV against job | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| View ATS score + report | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Improve CV with AI | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Generate cover letter | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Download improved CV | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Download cover letter | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Buy credits with Paddle | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ |
| View credit balance + history | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Browse visa-sponsored jobs | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Browse funded scholarships | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Generate SOP | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Generate research proposal | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Check credential equivalence | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Fraud filter blocks scams | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |

---

## 5. LIVE PREVIEW VERIFICATION LOG

| Component | URL | Last Verified | Screenshot | Console Errors | Status |
|---|---|---|---|---|---|
| Backend /health | http://localhost:8000/health | — | — | — | ⏳ |
| Backend /status | http://localhost:8000/status | — | — | — | ⏳ |
| Frontend home | http://localhost:3000 | — | — | — | ⏳ |
| Dashboard | http://localhost:3000/dashboard | — | — | — | ⏳ |
| Workspace | http://localhost:3000/workspace | — | — | — | ⏳ |
| ATS scan | http://localhost:3000/ats | — | — | — | ⏳ |
| CV improvement | http://localhost:3000/improve | — | — | — | ⏳ |
| Cover letter | http://localhost:3000/cover-letter | — | — | — | ⏳ |
| Credits | http://localhost:3000/credits | — | — | — | ⏳ |
| Credits purchase | http://localhost:3000/credits/purchase | — | — | — | ⏳ |
| Jobs list | http://localhost:3000/jobs | — | — | — | ⏳ |
| Scholarships | http://localhost:3000/scholarships | — | — | — | ⏳ |
| Credentials | http://localhost:3000/credentials | — | — | — | ⏳ |
| Status page | http://localhost:3000/status | — | — | — | ⏳ |
| Waitlist | http://localhost:3000/waitlist | — | — | — | ⏳ |

> 0/6 MCP servers available this session. Fallbacks per master prompt
> Part 13: curl + headless chrome + pytest.

---

## 6. E2E TEST STATUS

| Test | File | Last Run | Result | Notes |
|---|---|---|---|---|
| Job pipeline | tests/e2e/test_job_pipeline.py | 2026-10-06 | ✅ | 8 journeys (happy path + UK register match, markdown profile, closed listing, fraud block, injection, robots, AU pending, unknown country); all hosts pinned to fixtures |
| Scholarship pipeline | tests/e2e/test_scholarship_pipeline.py | 2026-10-06 | ✅ | 7 journeys (happy path with both schemas validated, window never gates, sub-bachelor honesty, no-education honesty, markdown background, unknown program, sparse-input refusal); `httpx.Client.request` patched to fail on any network call |
| Checkpoint recovery | tests/e2e/test_checkpoint_recovery.py | — | ⏳ | — (not created) |
| Circuit breaker | tests/e2e/test_circuit_breaker.py | — | ⏳ | — (not created) |
| Multi-provider failover | tests/e2e/test_multi_provider_failover.py | — | ⏳ | — (not created) |
| Paid model switching | tests/e2e/test_paid_model_switching.py | — | ⏳ | — (not created) |
| Workspace isolation | tests/e2e/test_workspace_isolation.py | — | ⏳ | — (not created) |
| ATS scan flow | tests/e2e/test_ats_journey.py | 2026-10-09 | ✅ | 3 journeys (offline scan with touched-host pin + persisted report, robots refusal, API scores a stored upload); run 13 named the file `test_ats_journey.py` to keep test basenames unique |
| CV improvement | tests/e2e/test_cv_improvement.py | — | ⏳ | — (not created) |
| Cover letter | tests/e2e/test_cover_letter.py | — | ⏳ | — (not created) |
| Credit system | tests/e2e/test_credit_system.py | — | ⏳ | — (not created) |
| Credit purchase | tests/e2e/test_credit_purchase.py | — | ⏳ | — (not created) |
| User onboarding | tests/e2e/test_user_onboarding.py | — | ⏳ | — (not created) |
| Full user journey | tests/e2e/test_full_journey.py | — | ⏳ | — (not created) |

> Unit tests (separate from E2E): 42 files / **436 passing** (run 13,
> 2026-10-09). Engine line coverage: **93%** (4398 statements, 304
> missed) — now *including* the tested `engine/ats/` package (parser
> 93%, scoring 97%, keywords 99%). Verified via
> `python -m pytest --cov=engine`. All three `tests/e2e/` files run
> offline (MockTransport / network pinned dead) and are collected with
> the unit suite. `ruff check` + `ruff format --check` + `mypy` clean
> repo-wide (the §12 lint/type debt stays cleared — run 13 re-verified
> the gate across all 108 files / 59 source modules).

---
## 7. AUDIT FAILURES

Tasks marked complete in `state.json` but failing verification:

| Task | Claimed | Actual | Reason | Action |
|---|---|---|---|---|
| 5.4 | ✅ Complete (local `state.json` edit, 2026-10-09) | sitemap route only | No schema.org/JSON-LD anywhere; `layout.tsx` metadata still the create-next-app default; "SEO" task not evidenced by files | Reopened to ⏳ pending in session 11 audit; implemented in run 19 (Phase 5 closeout) |

---

## 8. BLOCKED TASKS

| Task | Reason | Blocked Since | Attempts | Resolution Plan |
|---|---|---|---|---|
| — | — | — | — | — |

---

## 9. COMMIT & PUSH LOG (last 50)

| Commit | Task | Message | Pushed to main | Pushed to vantia-state |
|---|---|---|---|---|
| `4c84504` | — | vantia: phase 0 baseline - engine core, 96-test suite, workflows, tracking layer | ✅ | — |
| `974dde8` | — | vantia: phase 0 tracking update (run 1) | ✅ | — |
| `279c3ca` | 0.0, 1.5–1.7 | vantia(0.0,1.5,1.6,1.7): LLM stack + Paddle migration (run 1) | ⏳ blocked | — |
| `76867be` | state | vantia(state): 1.5-1.7 complete (run 2, 279c3ca) | — | ⏳ blocked |
| `3a672e7` | docs | vantia(docs): record run-1 LLM stack + Paddle migration (1.5-1.7, task 0.0) | ⏳ blocked | — |
| `1707db2` | 0.0 | vantia(0.0): finish Stripe purge - Phase-12 catalogue names -> Paddle | ⏳ blocked | — |
| `6c3458e` | state | vantia(state): Phase-12 catalogue names Stripe -> Paddle | — | ⏳ blocked |
| `001b78e` | 1.1–1.4 | vantia(1.1,1.2,1.3,1.4): schemas + prompt templates v1 (run 3) | ⏳ blocked | — |
| `98ffe3d` | state | vantia(state): 1.1-1.4 complete (run 3, 001b78e) | — | ⏳ blocked |
| `0c95ef6` | docs | vantia(docs): record run-3 Phase 1 closeout (1.1-1.4) | ⏳ blocked | — |
| `902c115` | 2.1 | vantia(2.1): fetch base + robots.txt + rate limiting (run 4) | ⏳ blocked | — |
| `afd352c` | state | vantia(state): 2.1 complete (run 4, 902c115) | — | ⏳ blocked |
| `6f4a5bb` | docs | vantia(docs): record run-4 Phase 2 start (2.1) | ⏳ blocked | — |
| `8dbcdec` | 2.2 | vantia(2.2): portal adapters W/G/L on shared fetcher (run 5) | ⏳ blocked | — |
| `6ded3c8` | state | vantia(state): 2.2 complete (run 5, 8dbcdec) | — | ⏳ blocked |
| `966fa1b` | docs | vantia(docs): record run-5 portal adapters (2.2) | ⏳ blocked | — |
| `2272dc7` | 2.3 | vantia(2.3): sponsor registers UK/AU/DE, DE gov jobs API, 50-country DB, repo sweep (run 6) | ⏳ blocked | — |
| `08b5b0e` | state | vantia(state): 2.3 complete (run 6, 2272dc7) | — | ⏳ blocked |
| `df67681` | 2.3 follow-up | vantia(2.3): all-country register coverage (50 European + AU dispatch, run 7) | ⏳ blocked | — |
| `e21bc6d` | state | vantia(state): 2.3 follow-up complete (run 7, df67681) | — | ⏳ blocked |
| `bb8d7e3` | 2.4, 2.8, 2.9 | vantia(2.4,2.8,2.9): credential equivalence + wired job pipeline + offline E2E (run 9) | ⏳ blocked | — |
| `ddbbfc7` | state | vantia(state): 2.4,2.8,2.9 complete (run 9, bb8d7e3) — Phase 2 closed 9/9, 25/88 total | — | ⏳ blocked |
| `f299b00` | 3.1, 3.4, 3.5 | vantia(3.1,3.4,3.5): scholarship database + credential mapper + window tracker (run 10) | ⏳ blocked | — |
| `16172ec` | state | vantia(state): 3.1,3.4,3.5 complete (run 10, f299b00) — 28/88 total, Phase 3 3/7 | — | ⏳ blocked |
| `3821a8e` | 3.2, 3.3, 3.6, 3.7 | vantia(3.2,3.3,3.6,3.7): SOP + research proposal generators, wired scholarship pipeline, E2E (run 11) | ⏳ blocked | — |
| `86f713a` | state | vantia(state): 3.2,3.3,3.6,3.7 complete (run 11, 3821a8e) — Phase 3 closed 7/7, 32/88 total | — | ⏳ blocked |
| `b6a5cad` | 4.1, 4.2, 4.3, 4.4, 4.5 | vantia(4.1,4.2,4.3,4.4,4.5): domain verification, tamper-evident idempotency, cross-run chain audit, incident reporter, Supabase schema (run 12) | ⏳ blocked | — |
| `dbf0ef5` | state | vantia(state): 4.1,4.2,4.3,4.4,4.5 complete (run 12, b6a5cad) — Phase 4 closed 5/5, 37/88 total | — | ⏳ blocked |
| `9775b07` | 5.1, 5.2 | feat(cli): implement full CLI command surface with apply, resume, verify, and reset functionalities | ⏳ blocked | — |
| `1efcae1` | 5.3 | vantia(5.3): Next.js web skeleton - adopt untracked web/ (session 11 audit) | ⏳ blocked | — |
| `2020baf` | state | vantia(state): audit - 5.4 reopened (SEO unevidenced), 5.1-5.3 backfilled, manifest run-12 appended - 40/88 | — | ⏳ blocked |
| `1afe5d3` | docs | vantia(docs): session 11 audit - restore Phase 2-5 task rows + sessions, adopt build board, backfill changelog/memory-bank/README | ⏳ blocked | — |
| `ba616fa` | 9.1–9.6 | vantia(9.1,9.2,9.3,9.4,9.5,9.6): ATS parser + 12-point scoring + keyword gaps + /ats/score API + run_ats_scan + E2E (run 13) | ⏳ blocked | — |
| `d6f3287` | state | vantia(state): 9.1,9.2,9.3,9.4,9.5,9.6 complete (run 13, ba616fa) - Phase 9 closed 6/6, 46/88 total | — | ⏳ blocked |

> ⏳ **Push blocked this session (and session 3).** The environment's
> cached GitHub credential is `denisprosperous`, an account without
> access to `paulocortex5-lgtm/Vintia` (HTTP 403, no `gh` CLI, no
> stored token). All commits exist locally and are ready to push with
> the inline credential documented in `docs/RUNBOOK.md`:
>
> ```bash
> git push https://oauth2:<token>@github.com/paulocortex5-lgtm/Vintia.git main
> git push https://oauth2:<token>@github.com/paulocortex5-lgtm/Vintia.git vantia-state
> ```

---

## 10. SESSION LOG

> **Session/run reconciliation (audited session 7):** sessions and runs
> are *different* counters. The header's **Session count (7)** counts
> human-led sessions; `.vantia/run_manifest.json` holds **6 runs** with
> session fields `[1, 3, 4, 5, 6, 7]` — session 2 completed no run, so
> it has no manifest entry. §10 below lists all 7 sessions (S1–S7); the
> log previously showed only S3–S7 (5 entries; 4 before S7 was logged),
> which is the source of the "4 vs 7" discrepancy reported in the audit.

### Session 1 — 2026-10-03 — Phase 0 baseline (0.1–0.9): engine core, 96-test suite, tracking layer

| Item | Outcome |
|---|---|
| 0.1–0.9 | Repo scaffold (pyproject, Dockerfile, `bootstrap.sh`, env files), engine core (state manager, locking, idempotency, hash chain, cost tracker, structured logging, error taxonomy, retry/backoff), Supabase persistence + write-through mirror + local fallback, FastAPI `/health` + keep-alive workflows, 96-test suite |
| State | Seed v4.0 (88 tasks / 14 phases), `run_manifest.json`, `vantia-state` orphan branch (`aa0f228`); run 1 recorded |
| Tests | 96/96 passing, 97% engine coverage |
| Commits | `4c84504` + `974dde8` (main), `aa0f228` + `903bc56` (vantia-state) |

### Session 2 — 2026-10-04 — planning & alignment (no code run)

| Item | Outcome |
|---|---|
| Planning | Master prompt v6.0 assessment; task-count reconciliation (prompt header 98 / assessment 99 incl. 0.0 / seed catalog 88 → **88** stays the denominator, §12); free-tier stack confirmation |
| State | **No run recorded** — the window between S1 (run 1) and S3 (run 2) contains no code commits on `main`, so session 2 produced no `end_run`; the manifest's session list is therefore `[1, 3, 4, 5, 6, 7]`. Entry marked *reconstructed* — no state commit exists for it |

### Session 3 — 2026-10-04 — Phase 1 LLM stack (1.5/1.6/1.7) + Stripe→Paddle purge (task 0.0)

| Item | Outcome |
|---|---|
| 1.5 `providers.yaml` | 22 providers (12 free / 10 paid) with openai / gemini / anthropic / cohere payload styles; add a provider = edit YAML only (R38) |
| 1.6 router + quota | `pick()` free-before-paid chain (R27), skips providers without keys or with exhausted quota; `QuotaTracker` daily rollover, rpd/rpm caps, optional Supabase `llm_usage` mirror |
| 1.7 client + json_utils | `LLMClient.complete()` / `run_chain()` failover (429 → next provider), dry-run with zero network I/O (R25), `VANTIA_MAX_COST_USD` ceiling (R18), hash-chained envelope (R24); `strip_fences`, `canonical_json`, `safe_parse` |
| 0.0 Stripe → Paddle | Every `STRIPE_*` reference removed repo-wide; added `PaddleError`, `paddle_client` (checkout transactions), `paddle_webhook` (HMAC-SHA256 + 5 s replay window + `paddle_events` idempotency), `docs/PADDLE_SETUP.md`. Follow-up: the Phase-12 catalogue task names in `engine/seed/state.json` + `.vantia/state/state.json` were still "Stripe …" and are now renamed to Paddle (12.1/12.2/12.3/12.6) |
| Bug found & fixed | `QuotaTracker.usage_snapshot()` held a non-reentrant `threading.Lock` while calling `remaining_rpd()` / `check_quota()`, which re-acquire it → deadlock that hung the test run. Switched to `threading.RLock` |
| Tests | 18 files / 165 passing / 91% `engine/` line coverage (`pytest --cov=engine -q`) |
| Lint & types | All new + touched files: `ruff check` clean, `ruff format --check` clean. Repo-wide debt in untouched modules is tracked in §12 |
| Push | ❌ blocked (403 — cached credential lacks access to `paulocortex5-lgtm/Vintia`); commits `279c3ca` (main) and `76867be` (vantia-state) are ready locally — see §9 |

### Session 4 — 2026-10-04 — Phase 1 closeout (1.1–1.4): schemas + prompt templates v1

| Item | Outcome |
|---|---|
| 1.1 Envelope + ATS schema | `envelope.schema.json` reworked to the exact runtime contract: required keys are `ENVELOPE_FIELDS` (17) in emission order, `artifact_hash` (payload) vs `envelope_hash` (tamper-evident) split, nullable `prev_hash`; `build_envelope()` now emits `schema_version`/`task_id`/`created_at`/`payload` plus token/cost/dry-run fields. `ats_score.schema.json` (shipped in phase 0) unchanged |
| 1.2 SOP schema | `sop.schema.json`: content ≥ 200 chars, ≥ 3 sections, tone enum (formal/professional/narrative/confident); round-trip + 2 negative tests |
| 1.3 Research proposal schema | `research_proposal.schema.json`: title/research_question/abstract length floors, 3–10 keywords, timeline phases 1–48 months, degree_level enum; round-trip + 3 negative tests |
| 1.4 Prompt templates v1 | 3 new templates (`v1_ats_score`, `v1_sop`, `v1_research_proposal`) join the 2 pre-existing ones; all 5 carry the `<security>` block, DATA-not-instructions and honesty guards; schema↔prompt tests assert the ATS prompt teaches all 12 category keys |
| Tooling | `ruff check` + `ruff format --check` clean on all touched files; `mypy` clean on touched files (fixed pre-existing `arg-type` error in `tests/test_llm_client.py`); standalone verification script `ALL CHECKS PASSED` |
| Tests | 18 files / 172 passing / 91% `engine/` line coverage (1422 statements, 123 missed) |
| State | run 3 recorded via `VantiaState` (lock → begin/complete → end_run); `run_manifest.json` backfilled with runs 2 + 3 (session 3 had left it at run 1 only) |
| Push | ❌ still blocked (403 — cached credential `denisprosperous`, no access to `paulocortex5-lgtm/Vintia`); commits `001b78e` (main) and `98ffe3d` (vantia-state) are ready locally — see §9 |

### Session 5 — 2026-10-04 — Phase 2 start: fetch base (task 2.1)

| Item | Outcome |
|---|---|
| 2.1 Fetch base | New `engine/sources/` package: `Fetcher.fetch()` pipeline = scheme allow-list → robots gate → per-domain rate limit (before **every** attempt incl. retries) → GET with exponential backoff on 5xx/timeout (`TransientFetchError`, added to the §14 error taxonomy) → size cap; 4xx and upstream 429 are terminal. `FetchResult` carries url/final_url/status/content/content_type/fetched_at/elapsed_ms |
| robots.txt | `RobotsCache`: one fetch per origin (TTL 6 h), documented status policy — 200 parse/enforce, 401/403 disallow-all, 404/410 allow-all, 5xx/429/network fail-open with a warning; robots.txt itself is fetched through the rate limiter, never through the gate |
| Rate limit | `DomainRateLimiter`: min-interval spacing + per-domain daily budget (UTC rollover), slot reserved under lock / slept outside it, `RateLimitError` with `resets_at` context when the budget is gone. All knobs env-configurable (`VANTIA_FETCH_*`, documented in `.env.example`) |
| Tests | +18 in `tests/test_sources.py` — 19 files / 190 passing / 91% coverage (1655 statements). Zero network I/O (`httpx.MockTransport`) and zero real sleeps (fake clock) |
| Tooling | `ruff check` + `ruff format --check` + `mypy` clean on all new/touched files; `bash -n bootstrap.sh` OK. Known repo-wide ruff debt unchanged (§12) |
| Follow-ups | HTTP response cache for `.vantia/cache/fetches` deferred (candidate for 2.8); portal-specific parsing lands in 2.2 |
| Push | ❌ still blocked (403, `denisprosperous`); `902c115` (main) + `afd352c` (vantia-state) ready locally — see §9 |

### Session 6 — 2026-10-04 — Phase 2: portal adapters W/G/L (task 2.2)

| Item | Outcome |
|---|---|
| 2.2 W/G/L adapters | New `engine/sources/portals/`: `PortalAdapter` ABC + `JobListing` (portal/id/title/company/location/url/posted_at/description/extra) + `GreenhouseAdapter` (`boards-api.greenhouse.io`, `content=true`, single-job `load()`) + `LeverAdapter` (`api.lever.co/v0/postings/{company}?mode=json`, single `/{company}/{uuid}`, EU hosts accepted, `descriptionPlain`) + `WorkdayAdapter` (`POST .../wday/cxs/{tenant}/{site}/jobs`, configurable `wd` label, detail `POST .../job/{id}`) + registry (`adapters_for`, `adapter_for_url`, `load_listing` with `unsupported_portal` code). W/G/L = **W**orkday/**G**reenhouse/**L**ever: the repo never expanded the abbreviation; endpoints verified against the public API docs this session |
| Fetcher change | Added `Fetcher.post()` — same robots gate + rate limit (incl. every retry) + backoff + size cap as GET, split out via `_request()`; +3 tests in `tests/test_sources.py` |
| text/dates | `strip_html()` (stdlib HTMLParser, drops script/style, unescapes first for Greenhouse); `iso_date()` (ISO + English month shapes via direct `date()` construction, no naive-datetime lint) + `epoch_ms_date()` |
| Tests | +14 in `tests/test_portals.py` (realistic fixtures, MockTransport only): params/bodies asserted per portal, robots respected, defects probed (404, unknown host) — 20 files / 207 passing / 92% `engine/` coverage (1920 statements, 163 missed) |
| Tooling | `ruff check` + `ruff format --check` + `mypy` clean on all new/touched files (defensive payload-shape guards added; `Fetcher.post` body assertion fixed after compact-JSON find) |
| Env rebuild | The `/tmp/vantia-venv` was wiped between sessions (`/tmp` volatility); rebuilt as the persistent project `.venv` (gitignored) with identical pinned versions (pytest 9.1.1, ruff 0.16.10, mypy 2.4.0). Future sessions must use `.venv/bin/python`, not `/tmp/vantia-venv` |
| Push | ❌ still blocked (403, `denisprosperous`); `8dbcdec` (main) + `6ded3c8` (vantia-state) ready locally — see §9 |

### Session 7 — 2026-10-05 — 2.3 + product direction: gov jobs, all-Jobs (not sponsorship-only), Europe DB, targeting

**User-initiated product direction (all implemented, see `docs/SOURCES.md`):**

1. Government job portals are first-class: German Federal Employment Agency API adapter (endpoint/headers verified live, including the reason plain requests get 403), every EU country's public employment portal catalogued.
2. Active-only: listings with past closing dates are dropped (`filter_active` in every search, `ensure_active` in every `load()` → `listing_inactive`).
3. No sponsorship gating: the platform fetches **all** jobs; sponsorship is a tag (`visa_sponsorship: True/False/None`), never a filter. Registers badge employers, never drop listings.
4. All European countries: 50-entry database (`engine/sources/countries.py`) + `search_targets()` ranking for opportunity + less competition (structural first; Eurostat `unemployment_rate` hook is `None` until a verified snapshot ships — no invented stats).

| Item | Outcome |
|---|---|
| 2.3 registers (UK/DE/AU) | `engine/sources/registers.py`: UK GOV.UK CSV pipeline verified (daily 10.4 MB register); AU raises `RegisterPending` until the mandated register exists (deadline 2026-10-08); DE documented as no-public-register (`GERMANY_PUBLISHES_REGISTER=False`); fuzzy employer matching + `badge()` tagging |
| Government jobs | `engine/sources/government.py`: AA search (`was/wo/umkreis/page/size`) + detail via base64 `refnr` path; active filtering; full-body defensive parsing across AA v4 key spellings |
| Countries DB | 50 entries w/ PES URLs, API status, register status; EU-27 completeness test; DE-first ranking |
| Tests | +24 (test_countries / test_registers / test_government / +2 portals active-only): 23 files, 231 passing, 92% coverage; MockTransport only |
| Sweep | `ruff check` + `ruff format --check` + `mypy` now **all** clean repo-wide (60 files) — the §12 legacy debt is gone; tests green after the sweep (231) |
| Push | ❌ still blocked (403); `2272dc7` (main) + `08b5b0e` (vantia-state) ready locally |
| **Session 7 continued (audit closeout)** | User audit: (1) register layer must cover **all** countries of interest, not the labelled three → `RegisterSpec` registry + `fetch_register()`/`fetch_registers()` dispatch in `registers.py`: every one of the 50 database countries + AU resolves (GB published → generic page→CSV pipeline; AU pending → `RegisterPending`; all others → empty register, never a gate). Future published registers plug in as one data row. (2) §10 backfilled with S1/S2 + session/run reconciliation (above). (3) `docs/SOURCES.md` register section → all-country coverage. +4 tests (dispatch, unknown-country, bulk pending-skip, 51-country coverage): **235 passing / 92% coverage**; ruff + mypy clean |

**Answer to the user's 2.3 question (recorded):** "2.3 visa register fetchers (UK/DE/AU)" = fetchers for *government employer-license lists* used to badge sponsors — not job boards, and not a job filter. The UK/DE/AU label is a planning artifact (founding markets when 2.3 was written); *coverage* is all countries of interest — see "Session 7 continued" above and `docs/SOURCES.md` §"Register coverage".

---

### Session 8 — 2026-10-05 — Security guardrails + ATS resume generator (2.5, 2.6, 2.7)

**LLM note (user asked to "cycle through all available LLMs and exhaust tokens"):** the environment has **zero LLM API keys** — there is no `.env`, no key is set in the shell environment, and every value in `.env.example` is a placeholder. There is no token supply to exhaust, so nothing was burned and no provider was contacted. Instead the work was written so the LLM path lights up the moment credentials land: `engine/llm/router.pick()` builds the failover chain, `LLMClient.run_chain()` executes it, and `VANTIA_DRY_RUN=1` keeps every path deterministic offline.

| Item | Outcome |
|---|---|
| 2.6 PII redactor | `engine/security/redact.py`: 8 kinds (email, phone, NINO, SSN, IBAN, credit card, secret/API key, URL credentials) with checksum validators (IBAN mod-97 via the standard decimal letter-substitution, Luhn for cards, NINO/SSN format guards) so ordinary digits and words survive; idempotent, offsets index the *original* text, `kinds=` narrowing |
| 2.6 injection guard | `engine/security/injection.py`: weighted phrase corpus (instruction-override / secret-extraction / marker / authority / obfuscation / tool-spoof) over normalized text — casefold + whitespace collapse + zero-width stripping defeats trivial obfuscation; `trusted` mode never auto-blocks user-owned input, `untrusted` (default) raises `InjectionDetectedError` at score ≥ 2.0 |
| 2.5 fraud filter | `engine/security/fraud.py`: scores a `JobListing` for fee-to-candidate / visa-mill / guarantee / payment-red-flag / urgency text signals plus risky-TLD contacts and posting-vs-contact domain mismatch; verdicts clean / review / block; `fraud.block()` raises `FraudSignalError`. Tag-and-warn: signals never silently drop a job (session 7 policy) |
| 2.7 ATS resume generator | `engine/generators/resume.py`: deterministic tailoring (job-matched skills first, ATS-safe plain markdown, no tables/HTML) ships with **no provider, no key, no network**; optional LLM polish via `LLMClient.run_chain` with the untrusted posting PII-redacted before it enters the prompt, injection + fraud guards up front, graceful fallback to the deterministic layer on `AllProvidersExhausted`, and the R24 hash-chained envelope when a client is supplied |
| Tests | +27 (15 security, 12 resume): **262 passing** (was 235); `ruff check` / `ruff format --check` / `mypy` clean on 68 source files |
| Design note | Deterministic-first: every generator ships without a provider. The LLM is an accelerator, not a dependency — `generate_resume(candidate, listing)` is the shippable path |
| Push | ❌ still blocked (403); `1e40b27` (main) + state commit ready locally |

---

### Session 9 — 2026-10-06 — Phase 2 closeout: equivalence, job pipeline, E2E (2.4, 2.8, 2.9)

**Operating note (user direction):** loop continuously through the remaining task batches without stopping after each pass, and keep the working board (current task + next queue) visible every cycle.

| Item | Outcome |
|---|---|
| 2.4 credential equivalence | `engine/credentials/`: 28-row registry with per-row `basis` provenance (GOV.UK levels, UHR/ENIC-Sweden HND assessment: 240 CATS = 120 ECTS + NQF 5 = EQF 5, French RNCP, German DQR, Bologna cycles). `lookup()/describe()/equivalence()` rank exact → contained → covered-token (stopword-guarded so a bare "degree" never matches "foundation degree"); `eqf_level` asserted **only** where a verified crosswalk exists — A level / NVQ rows carry `None` + ENIC-NARIC advice; NG OND/HND are honest gaps. `degree_in_country()` places levels 5–8 in GB/FR/DE/IE/SE/CA/AU (Bologna/AQF/NFQ names). `gpa_to_ects()` ratio bands (0.90/0.80/0.70/0.60/0.50), any scale, validated. `remote_lookup()` via Fetcher with owner-configured `VANTIA_EQUIVALENCE_ENDPOINT` — refuses when unset (no guessed URLs) |
| 2.8 job pipeline | `engine/pipeline.py: run_job_pipeline` wired end to end: `load_listing` (robots + rate limit + closed-refusal) → belt-and-braces `filter_active` → `fraud.assess` (clean/review pass with report attached, block raises) → register badge (`published` fetch, `pending`/`unknown` degrade with reason recorded, never fatal) → `load_profile` → `generate_resume` (deterministic ship path; optional LLM polish). Result payload: `pipeline/job/fraud/sponsorship/resume` |
| 2.8 profile loader | `engine/generators/profile.py: load_profile` — `.json` (typed fields, comma/object skills, unknown keys ignored) and `.md`/`.txt` (heading name/title with section-stopword guard, Skills bullet/comma extraction); refuses `profile_file_missing` / `profile_format_unsupported` / `profile_parse_error` |
| 2.9 E2E | `tests/e2e/test_job_pipeline.py` — 8 journeys on `httpx.MockTransport`, zero network: full path with UK register match (Acme Robotics Ltd badge), markdown profile, closed listing, fraud block (score ≥ 4), injection abort, robots disallow, AU pending (deadline recorded, portal-only traffic), unknown country. Touched-host assertion pins footprint to fixture hosts |
| Tests | +28 (13 credentials, 6 profile, 8 E2E, +1 net pipeline): **290 passing**, 28 files, **93% engine coverage** (2860 stmts); `ruff check` / `ruff format --check` / `mypy` clean (74 files) |
| State | Phase 2 **9/9 complete**; 25/88 total; run 9 closed; manifest backfilled with runs 7–9 (they had never been recorded) |
| Tooling note | Session start hung300 s on `git log` → leftover pager (`less`) processes held the terminal; fixed by `git --no-pager` + killing strays. `state.start_run()` returns the history **entry**, not the id — pass the literal run number to `end_run` |
| Push | ❌ still blocked (403); `bb8d7e3` + `ddbbfc7` ready locally |

**Run 10 (same session) — Phase 3 data layer (3.1, 3.4, 3.5):**

| Item | Outcome |
|---|---|
| 3.1 scholarship database | `engine/scholarships/database.py` — five programs with **verified official URLs** (Chevening + timeline, Commonwealth CSC, DAAD database, Erasmus+ EMJM, Australia Awards/DFAT), every row carrying a `basis` provenance stamped `2026-10-06`; only Chevening (Aug→Oct) and EMJM (Oct→Jan) embed windows because only their official pages publish a recurring cycle — DAAD/Commonwealth/Australia Awards honestly say `unknown` instead of a guessed deadline. `search_scholarships()` filters field/level/host/nationality/funding; EMJM spans every Erasmus+ programme country via `spans_europe` |
| 3.4 credential mapper | `engine/scholarships/mapper.py` — `map_credential()` resolves the applicant's qualification through the 2.4 registry and compares `eqf_level` to `min_eqf_level`; verdict is **three-valued** (meets / falls short / `None` when unverified) with ENIC-NARIC advice — never a fabricated "you qualify" |
| 3.5 window tracker | `engine/scholarships/windows.py` — one symmetric annual algorithm (nearest-close vs nearest-open decides `closed` vs `upcoming`) that handles same-year and year-wrapping cycles identically, closing-day inclusivity, month-precision (`"YYYY-MM"` → whole-month close), fixed one-shot windows, and `unknown` when no window is embedded. Boundary-tested: day before open / open day / close day / day after close |
| Tests | +15 (`tests/test_scholarships.py`): **305 passing**, 29 files, 93% coverage (3026 stmts); ruff + mypy clean (79 files) |
| State | 28/88 complete; Phase 3 3/7; run 10 closed (`f299b00` code, `16172ec` state) |

**Run 11 (same session) — Phase 3 closeout (3.2, 3.3, 3.6, 3.7):**

| Item | Outcome |
|---|---|
| 3.2 SOP generator | `engine/generators/sop.py` — deterministic five-section SOP (Motivation/Background/Fit/Career Goals/Closing) built only from profile facts, scholarship facts and caller inputs; honest placeholder lines when material is missing; **validates against `sop.schema.json` on every path** (including a bad `tone` being refused). LLM polish renders the shipped `v1_sop.md`, accepts only schema-valid JSON, keeps `applicant_id`/`scholarship_id` ours; unparseable output keeps the deterministic payload; provider failure sets `fallback` |
| 3.3 research proposal | `engine/generators/proposal.py` — title/question from the caller's interests, abstract, 4-phase bounded timeline, 5 sections; **keywords derived only from real inputs** and `proposal_keywords_insufficient` refuses instead of faking index terms; validates against `research_proposal.schema.json`; same polish/fallback contract via `v1_research_proposal.md` |
| 3.6 scholarship pipeline | `engine/pipeline.py: run_scholarship_pipeline` — database lookup → `load_profile` → credential map of the latest education entry (three-valued, informational) → window status vs `today` (**never gates**) → SOP + proposal; payload `{pipeline, scholarship, credential, window, sop, proposal}` |
| 3.7 E2E | `tests/e2e/test_scholarship_pipeline.py` — 7 journeys with `httpx.Client.request` monkeypatched to fail on any network call; both artifact payloads validated against the shipped schemas; window-not-gating, sub-bachelor and no-education honesty, markdown background, unknown program, sparse-input refusal |
| Defects found by the tests | `safe_parse()` **raises** on unparseable LLM output (it does not return `None`) — both `_polish` paths now catch it; research question now embeds the specific research interests rather than the broad field |
| Tests | +21 (8 sop, 6 proposal, 7 E2E): **326 passing**, 32 files, 93% coverage (3289 stmts); ruff + mypy clean (84 files) |
| State | **Phase 3 7/7 closed**; 32/88 total; run 11 (`3821a8e` code, `86f713a` state) |

**Run 12 (session 10) — Phase 4 closeout (4.1, 4.2, 4.3, 4.4, 4.5):**

| Item | Outcome |
|---|---|
| 4.1 domain verification | `engine/verification/domain.py` — A + CNAME checks against a provider expectation table (`render`, `vercel`) via an **injectable resolver**, so tests never touch the network; `DomainReport` is serialisable for the status page; if `dnspython` is missing the report says `resolver_unavailable` **loudly** instead of reporting success. `dnspython` added to deps. `tests/test_domain_verification.py` |
| 4.2 idempotency tamper-evidence | `engine/idempotency.py` — every entry now carries an `entry_hash` (SHA-256 over its canonical JSON); `IdempotencyRegistry.verify()` recomputes all hashes and reports tampered **and** legacy unhashed entries ("unverifiable ≠ verified"); `entries()` added. `StepExecutor` keeps recording through the registry, so it is now tamper-evident |
| 4.3 cross-run chain audit | `engine/hash_chain.py` — `audit()` (ok / length / tip / first_bad_seq) and `record_run()`; any closed run can be appended to the append-only cross-run chain instead of living only in `state.json`. The run-12 record was written through these APIs (`audit()` reports `ok=True`, length 1) |
| 4.4 incident reporting | `engine/incidents.py` — a blocked task opens a GitHub issue via the `gh` CLI; when the CLI is absent or the 403 environment refuses it, the incident is written as an **offline Markdown draft + index entry** under `.vantia/issues/`, so no incident is ever lost. `StepExecutor(issue_opener=...)` / `_open_incident` is guarded so a failing reporter never masks the original block |
| 4.5 Supabase mirror | `supabase/migrations/0001_init.sql` — Postgres mirror of `.vantia/state.json` (`runs`, `tasks`, `artifacts`, `idempotency_registry` incl. the 4.2 `entry_hash` column, `hash_chain`, `incidents`, `task_progress` view) with CHECK-constrained statuses and JSONB payloads; sync is `INSERT ... ON CONFLICT`, never hand-edited. `tests/test_sql_schema.py` pins the DDL statically |
| CLI | `vantia status` now reports the 4.3 chain audit, the 4.2 registry integrity check, and accepts `--verify-domain --domain … --expect …` for the 4.1 DNS check |
| Defect found by the tests | Click silently renamed `--verify-domain` to `verify_domain`, which broke the callback with `TypeError: status() got an unexpected keyword argument` — fixed by declaring the parameter name explicitly (`"verify_domain_flag"`). This only surfaced once the CLI was actually invoked; an assertion-only test would not have caught it |
| Tests | +32 new tests across 6 suites (8 domain, 7 incidents, 8 SQL schema, +4 idempotency, +2 hash chain, +3 CLI/state): **358 passing**, 35 files, 93% coverage (3484 stmts); ruff check + format and mypy clean (90 files, 0 issues) |
| State | **Phase 4 5/5 closed**; 37/88 total; run 12 (`b6a5cad` code, `dbf0ef5` state). No LLM spend |

### Session 10 — 2026-10-07 — run 12 bookkeeping + CLI surface (5.1/5.2)

| Item | Outcome |
|---|---|
| Run 12 docs/state | `6c7ccfd` (docs) and `dbf0ef5` (state) recorded the Phase 4 closeout; content is the *Run 12* block above |
| CLI surface (unrecorded) | `9775b07` implemented the full CLI (`init / apply / status / resume / verify / reset`, 355 lines + 285 lines of tests) — landed **after** the run-12 docs commit and was never recorded in `state.json` / `PLATFORM_STATE.md` / manifest. Caught by the session 11 audit; 5.1/5.2 backfilled as ✅ |
| Manifest | run 12 was never appended to `run_manifest.json` (still ended at run 11) — backfilled in session 11 |

### Session 11 — 2026-10-09 — audit + reconciliation, then continuous build loop

**Operating note (user direction):** loop continuously through the remaining task batches without stopping after each pass; keep the working board (current task + next queue) visible every cycle; update every progress `.md` while moving.

| Item | Outcome |
|---|---|
| Drift found | (a) local `PLATFORM_STATE.md` edit had reverted §3 rows for Phases 2–5 to ⏳ and deleted §10 sessions 1/2/5–9 — restored from HEAD `6c7ccfd`; (b) local `state.json` edit claimed 5.1–5.4 complete — 5.1/5.2/5.3 **verified** (`9775b07`, `1efcae1`), 5.4 **failed** verification → reopened (§7); (c) untracked `engine/ats/` — 9.1/9.3 written but untested, 9.2 `scoring.py` had a fatal `SyntaxError` so `import engine.ats` failed; (d) manifest missing run 12; (e) CHANGELOG stuck at Run 1, memory-bank stale |
| Reconciliation | 40/88 complete (45%); `web/` adopted as 5.3 (`1efcae1`); `docs/BUILD_BOARD.md` adopted as the live in-flight/queue view; §1/§2/§3/§6/§7/§9 corrected |
| Verified baseline | 36 test files / **381 passing** / 0 failing; engine coverage **93%** excluding `engine/ats` (83% including it — 428 untested statements, covered by run 13); `ruff check engine` currently red on `engine/ats` only |
| Security | a GitHub classic token was pasted in chat → treated as **compromised**: never used, never written to the repo; rotate/revoke before the first push (§12) |
| Build loop | runs 13→21 queued in `docs/BUILD_BOARD.md`: Phase 9 → 10 → 11 → 12 → 8 → 6 → 5 (5.4–5.6) → 13 → 7 |

**Run 13 — 2026-10-09 — Phase 9 closeout (9.1–9.6): ATS scoring engine**

| Item | Outcome |
|---|---|
| 9.1 parser | `engine/ats/parser.py` repaired + hardened: `_strings` unbound-local crash on profiles without `languages`/`certifications` (any such JSON profile crashed!), `detect_format` never accepted MIME-tail hints so `content_type` uploads silently fell back to `txt`, extractor resolution moved inside the `try` so a missing `pypdf`/`python-docx` yields the friendly `resume_extractor_unavailable` install hint. Tests: JSON/markdown/DOCX round-trips, loud failures, contact/confidence honesty, span maths |
| 9.2 scoring | `engine/ats/scoring.py` rebuilt from the broken half-file: `CATEGORY_WEIGHTS` (12 categories = 100.0), deterministic rubric with explicit demand detection (years/cert/language/education/location rules), dated-facts-only spans, every sub-100 category ships a suggestion, `keyword_match` via the gap report. Payload validates against `ats_score.schema.json` on every path; deterministic across runs |
| 9.3 keywords | `engine/ats/keywords.py` tested + stemmer fixed: the `"es"` rule stripped `databases→databas` so plurals never matched (`database`) — replaced with sibilant handling + trailing-`s`; duplicate stopwords removed (ruff B033) |
| 9.4 API | `POST /ats/score` (422 stable codes for bad uploads vs 500 if *our* payload fails the schema) + `GET /status` (real state summary for the preview dashboard) |
| 9.5 pipeline | `run_ats_scan` implemented: store resolution with traversal guard, **parse before any network**, robots/rate-limit/closed-refusal via `load_listing`, deterministic score, schema validation, report persisted as `<file>.ats.json` |
| 9.6 E2E | `tests/e2e/test_ats_journey.py` — offline journey with touched-host pin (only `boards-api.greenhouse.io`), robots refusal, API-scores-a-stored-upload |
| Tooling | stale stub test `test_ats_scan_is_a_task_9_5_stub` replaced with wired-behavior test; `state.start_run()` return annotation corrected (`dict`, not `int` — the session-9 tooling note, now enforced by mypy); `domain.py` dnspython import rewritten mypy-clean; `ruff format` sweep (8 files); **ruff check + format + mypy all green repo-wide** |
| Tests | 42 files / **436 passing** / **93% coverage (4398 stmts, incl. engine/ats at 93–99%)**; no LLM spend |
| State | run 13 recorded; Phase 9 **6/6 closed**; 46/88 total (52%); manifest run 13 appended; commits `ba616fa` (code) + `d6f3287` (state) |

**Run 14 (session 12) — 2026-10-09 — Phase 10 closeout (10.1–10.6): CV improvement + cover letter**

| Item | Outcome |
|---|---|
| Reconciliation first | The board said 10.2/10.4/10.5/10.6 "queued" and this snapshot said Phase 10 0/6, but the working tree already contained all six tasks — the suite was run (462 green, 93% cov, gates clean) **before** anything was recorded |
| 10.1 / 10.3 prompts + schemas | audit-verified: `v1_cv_improve.md` + `cv_improvement.schema.json`, `v1_cover_letter.md` + `cover_letter.schema.json` already shipped and tested (`tests/test_prompts.py`, `tests/test_schemas.py`) → recorded ✅ |
| 10.2 CV improver engine | `engine/improve/cv.py` — deterministic fact-preserving edits only: canonical section rebuild (structured JSON profile → real CV), honest placeholder lines, keyword mirroring **only** for words evidenced in the resume (a JD keyword with no evidence is never added — not even as a suggestion), sanctioned weak-verb swaps + filler removal, capped at 30 priority-ranked improvements; summary counts are always recomputed from the shipped list; optional LLM polish re-validates against the schema and re-stamps `original_cv_id`. `run_cv_improvement` wired in `engine/pipeline.py` (store resolution + traversal guard + `<file>.improve.json`) |
| 10.4 cover-letter generator | `engine/generators/cover.py` — facts-only letter: real title/employer (omitted when unknown, never `[Company]`), ≤2 **verbatim** quantified bullets (Achievement section dropped rather than faked when absent), matched keywords spelled the way the resume spells them, no fake availability/contacts; polish path keeps our `resume_id`/`job_id`/metadata and recounts word counts. `run_cover_letter` wired (posting via `load_listing` with robots/rate-limit/closed-refusal, `<file>.cover.json`) |
| 10.5 / 10.6 E2E | `tests/e2e/test_cv_improvement_flow.py` + `tests/e2e/test_cover_letter_flow.py` — offline journeys: store resolution, traversal refusal, schema validation on every path |
| Tests | +4 suites (+2 unit, +2 E2E): **462 passing**, 47 files, **93% coverage (4807 stmts)**; new modules `cover.py` 96% / `improve/cv.py` 92%; ruff + format + mypy clean |
| State | run 14 recorded; Phase 10 **6/6 closed**; 52/88 total (59%); manifest run 14 appended; commit `1003b3e` (code) + state commit |

**Run 15 (session 12) — 2026-10-09 — Phase 11 closeout (11.1–11.6): Credit System**

| Item | Outcome |
|---|---|
| 11.1 ledger + balance tables | `engine/credits/ledger.py` — local-first append-only ledger (`$VANTIA_CREDITS_DIR/ledger.json`), every movement an entry with signed amount + `balance_after` + caller `ref`, **idempotent by `(user_id, ref)`** (replay moves no money), R46 `InsufficientCredits` writes nothing, thread-safe atomic writes, best-effort Supabase mirror (`credit_ledger`/`credit_balances`, never raises); `supabase/migrations/0002_credits.sql` with `check (balance >= 0)`, kind CHECK matching `ENTRY_KINDS`, PK `(user_id, ref)` — static-tested incl. engine↔SQL parity. Corrupt store raises `ledger_corrupt` **loudly** (never resets balances — money must not vanish). `topup_from_paddle` keeps the webhook contract (idempotent per event, storage failure → `PaddleError` → `ledger_pending`) |
| 11.2 token metering | `engine/credits/metering.py` — `operation_cost()` prices from state `credits.token_costs` (unknown op → `unknown_operation` listing known prices, never silently free); `CreditMeter` = pre-flight (before work) + charge (on completion) + `metered()` context manager; estimate separates real `balance` from `available` (projected allowance, read-only). No USD↔token rate is invented anywhere |
| 11.3 tiers | `engine/credits/tiers.py` — free/pro/business read from state (10k/100k/1M), tier **recorded not inferred** (default free, `unknown_tier` refused), allowance granted exactly once per calendar month via ref `allowance:<user>:<YYYY-MM>`, `projected_balance()` shows unclaimed allowance without writing |
| 11.4 deduction on completion | `engine/pipeline.py` — `user_id` kwarg on `run_ats_scan`/`run_cv_improvement`/`run_cover_letter`: `_begin_charge` pre-flights (allowance + R46) **before any file/IO or fetch**, `_end_charge` charges only after schema-valid persistence; result carries `credits` (cost/balance_after/ref); no `user_id` → behavior unchanged (`credits: None`) |
| 11.5 balance API + UI data | `GET /credits/balance` — one dashboard payload (balance, tier, allowance, operation prices, packs, recent entries); performs the idempotent monthly grant. `GET /credits/estimate` — read-only affordability with stable 422 codes (`user_id_required`, `operation_required`, `unknown_operation`) in `as_dict()` shape like 9.4. No auth yet — Phase 8 binds `user_id` to the session |
| 11.6 E2E | `tests/e2e/test_credit_journey.py` — offline journey: allowance → metered scan (2000) → metered improvement (8000) → **R46 refusal with zero network calls** → Paddle webhook double-delivery credits once → letter succeeds (5000) → estimate shortfall (3000) → balance payload kinds `[grant, spend, spend, topup, spend]`; touched-host pin. Plus `test_pipelines_without_user_id_stay_unmetered` |
| Stale test fixed | `test_paddle_webhook_records_event_and_is_idempotent` asserted the pre-Phase-11 `ledger_pending`/"unavailable" stub — rewritten to the wired behavior (`credited`/`ok`, exactly-once balance) |
| Tests | +5 suites (+4 unit, +1 E2E) +54 tests: **516 passing**, 52 files, **93% coverage (5120 stmts)**; ledger 98% / tiers 97% / metering 100% / config 93%; ruff + format + mypy clean |
| State | run 15 recorded; Phase 11 **6/6 closed**; 58/88 total (66%); manifest run 15 appended; commit `c1591d1` (code) + state commit |

**Run 16 (session 12) — 2026-10-10 — Phase 12 closeout (12.1–12.6): Credit Purchasing**

| Item | Outcome |
|---|---|
| Reconciliation first | Board said run 16 "in flight / queued", snapshot + state said Phase 12 0/6 and manifest ended at run 15 — while the working tree already held the full Phase 12 commit `e9146e9`. Gates re-run (540 green, 94% cov, ruff/format/mypy clean) **before** recording |
| 12.1 setup doc | `docs/PADDLE_SETUP.md` audited against code: fixed phantom `/api/*` route paths → real `POST /credits/checkout` + `POST /paddle/webhook`; documented dashboard-level return URLs (verified the installed SDK's `CreateTransaction` has no per-transaction success/cancel fields); flow diagram now matches the run-15 ledger + both migrations; verify section adds the new pytest gates **and the web build gate**; CORS + `VANTIA_ALLOWED_ORIGINS` documented. `.env.example`: added `NEXT_PUBLIC_ENGINE_URL` + `VANTIA_ALLOWED_ORIGINS` |
| 12.2 checkout endpoint | `POST /credits/checkout` — stable 422s (`user_id_required`, `unknown_pack` listing known packs) in `as_dict()` shape; Paddle/SDK/config failure → honest **502 `paddle_error`, never a fabricated URL**. `paddle_client`: dead `success_url`/`cancel_url` params removed (SDK-surface verified); `custom_data {user_id, pack_id, credits}` pinned by test through a faked SDK client |
| 12.3 webhook handler | audit-verified existing handler (signature R49, idempotency R50, ledger crediting since run 15) **plus** the missing route: `POST /paddle/webhook` (raw body, `Paddle-Signature` header, 400 on bad signature, 5 s-window handler unchanged) |
| 12.4 top-up idempotency | layered exactly-once: `paddle_events.event_id` dedupe + ledger ref `paddle:<event_id>`; **gap closed**: `supabase/migrations/0003_paddle.sql` created the `paddle_events` table the doc had promised since Phase 5 but never existed — static-tested against the handler's exact upsert columns and status vocabularies, plus R56 no-Stripe check |
| 12.5 purchase UI | `GET /credits/packs` (packs + prices + environment; honest `price_usd: null` if state lacks prices); `web/app/credits/purchase/page.tsx` (packs list, engine-reachable errors verbatim, user id in localStorage **labelled as Phase-8-auth placeholder**); engine CORS (`VANTIA_ALLOWED_ORIGINS`, default localhost:3000, never `*`) with preflight/allow/refuse tests. **Build gate:** `npm install` + `next build` run for the first time — found a **pre-existing 5.3 defect** (`sitemap.xml/route.ts` `export const dynamic` incompatible with `cacheComponents`) and fixed it; build now EXIT=0 |
| 12.6 purchase E2E | `tests/e2e/test_paddle_purchase_flow.py` — fully offline: packs UI data → checkout URL (SDK faked) → webhook credits 50 000 → redelivery no-op → `payment_failed` records without crediting → forged signature 400 → balance payload `[grant, topup]` + estimate reflects purchased credits |
| Drift closed | `.env.example` documented `VANTIA_FREE_TIER_TOKENS` etc. but **no code read them** — `load_credits_config` now applies them as env overlays (12-factor), invalid values raise `credits_config_invalid` loudly |
| Tests | +3 suites +24 tests: **540 passing**, 55 files, **94% coverage (5177 stmts)**; `engine/api.py` 97%, paddle webhook 85%; ruff + format + mypy clean; **web `next build` EXIT=0** |
| State | run 16 recorded; Phase 12 **6/6 closed**; 64/88 total (73%); manifest run 16 appended; commit `e9146e9` (code) + state commit |

---

## 11. NEXT SESSION ACTIONS

1. **Run 17 — Phase 8 (User Workspaces), in flight:** 8.1 Supabase Auth integration (`engine/auth/` — JWT extraction/refresh, offline-verifiable), 8.2 profile + workspace tables migration, 8.3 RLS policies + JWT hook, 8.4 private file storage, 8.5 workspace isolation E2E — all statically tested against an in-memory fake Supabase (no real credentials in this environment)
2. **Queue (continuous loop, see `docs/BUILD_BOARD.md`):** run 18 Phase 6 → run 19 Phase 5 closeout (5.4/5.5/5.6) → run 20 Phase 13 → run 21 Phase 7 acceptance
3. 4.5 follow-up: the Supabase mirror schema is written and static-checked, but RLS policies and a real `supabase db push` are untested until real credentials exist — do not claim the migration as applied
4. 2.3 follow-up (carried): fold `FederalEmploymentAgency` into a government-sources registry so `adapters_for()` and the register dispatcher share one per-country source table (`docs/SOURCES.md` checklist step 2)
5. 2.8 follow-up (carried): `run_job_pipeline` loads by URL for W/G/L portals only — government sources are harvested through their adapters and need a detail loader before they are addressable by direct URL (documented in the `run_job_pipeline` docstring)
6. Registers: new published country register = **one data row** in `registers._REGISTER_SPECS` (+ status flip in `countries.py`); verify before claiming "live"
7. Push: **rotate the disclosed token first** (see §12), then retry; 403 since session 3 with the cached credential; all code/state/docs commits exist locally
8. LLM credentials: add at least one free-tier key to `.env` so 2.7's LLM polish path and the R17/R18/R24/R25/R26/R27/R28 gates can be exercised against a live provider — today they are verified with `MockTransport` / a scripted `_FakeClient` only

> Dependency note for Phase 11: **resolved in run 15** —
> `engine/credits/ledger.py` now exists, so `handle_webhook()` records
> Paddle top-ups with status `credited` (idempotent per `event_id`);
> `ledger_pending` only remains as the honest fallback when a storage
> write itself fails (`PaddleError`).

---

## 12. RISKS & OPEN QUESTIONS

| Risk | Impact | Mitigation |
|---|---|---|
| Render cold starts during keep-alive gaps | User-perceived latency | Two-layer keep-alive; add third layer if needed |
| Supabase free tier 7-day inactivity pause | Platform unusable | Keep-alive cron also pings Supabase |
| LLM provider rate limits | Task failure | Multi-provider failover chain |
| Paddle live keys not configured | No purchases possible | Defer until launch; use sandbox mode |
| Vercel free tier non-commercial | Legal issue if monetized | Document; upgrade when revenue starts |
| Master prompt header says 98 tasks (v6.0 assessment: 99, incl. Task 0.0), catalog lists 88 | Progress denominator confusion | `state.json` + `engine/seed/state.json` both define 88 tasks; use 88 until the prompt's catalog is re-cut. Task 0.0 (Stripe purge) was executed as cross-cutting work and is recorded in §10, not as a catalogue row |
| Provider/infra credentials are REPLACE_ME placeholders | Network-success paths untested | Insert real keys during launch prep |
| A GitHub classic PAT was pasted into chat in session 11 (cleartext) | Token is **compromised** — anyone with the log can use it | Never used and never written to the repo; **rotate/revoke on GitHub before the first push**, then push per `docs/RUNBOOK.md` with an inline `oauth2:<token>@…` URL only |
| No LLM API keys in this environment (no `.env`, all `.env.example` values are placeholders) | Every LLM call path runs dry-run only; live token / latency / 429 behaviour untested | Deterministic layers ship as the default path (2.7 falls back to it); add keys at launch prep and re-run the live-path tests |
| Pre-existing ruff/mypy debt in modules untouched this run (api.py, execute_step.py, retry.py, state_manager.py, test_execute_step.py) | Repo-wide lint/type gate not clean | ✅ **Cleared in run 6 (session 7):** `ruff check` + `ruff format --check` + `mypy` all pass on all 60 files. Nothing left to sweep |
| The other 49 European countries (all except GB) carry `sponsor_register="none"` (= *no known* public register, not *verified* absence — DE's "none" is the one documented fact among them) | Under-scored targeting if a country actually publishes one; wrong negative claim if it does not | The register layer already dispatches on the status (empty badge set, never a gate); when a register is discovered it's a one-row addition to `registers._REGISTER_SPECS` + a status flip in `countries.py` (session 7 follow-up, §11 item 5–6) |

