# VANTIA — PLATFORM STATE

**Last updated:** 2026-10-06T22:20:00Z
**Master prompt:** v6.0
**Session count:** 9
**Overall readiness:** 36%

---

## 1. SHIPPING READINESS SUMMARY

| Metric | Value |
|---|---|
| Tasks complete | 32/88 |
| Tasks in progress | 0 |
| Tasks blocked | 0 |
| Tasks pending | 56 |
| Audit failures | 0 |
| Live previews passing | 0 |
| E2E tests passing | 0/14 |
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
| 4 | Verification & Hardening | 0/5 | 0 | 0 | 5 | 0% |
| 5 | Product Surface | 0/6 | 0 | 0 | 6 | 0% |
| 6 | Observability & Deployment | 0/7 | 0 | 0 | 7 | 0% |
| 7 | Acceptance | 0/3 | 0 | 0 | 3 | 0% |
| 8 | User Workspaces | 0/5 | 0 | 0 | 5 | 0% |
| 9 | ATS Scoring Engine | 0/6 | 0 | 0 | 6 | 0% |
| 10 | CV Improvement + Cover Letter | 0/6 | 0 | 0 | 6 | 0% |
| 11 | Credit System | 0/6 | 0 | 0 | 6 | 0% |
| 12 | Credit Purchasing | 0/6 | 0 | 0 | 6 | 0% |
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
| 3.6 | pipeline.py: run_scholarship_pipeline | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 3.7 | E2E scholarship pipeline test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

### Phase 4 — Verification & Hardening

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 4.1 | Domain verification (DNS + CNAME) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 4.2 | Idempotency registry persistence | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 4.3 | Cross-run SHA-256 hash chain | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 4.4 | Circuit breaker + GitHub issue | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 4.5 | Supabase schema migration + RLS | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

### Phase 5 — Product Surface

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 5.1 | CLI: apply/status/resume/verify/reset | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 5.2 | Golden-file CLI tests | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 5.3 | Web UI skeleton (Next.js) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 5.4 | SEO: schema.org + sitemap | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
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
| 9.1 | Resume parser (PDF/DOCX extraction) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 9.2 | ATS scoring engine (12-point) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 9.3 | Keyword matcher + gap analysis | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 9.4 | ATS score schema + API | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 9.5 | ATS scan pipeline integration | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 9.6 | ATS scan E2E test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

### Phase 10 — CV Improvement + Cover Letter

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 10.1 | CV improvement prompt + schema | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 10.2 | CV improver engine | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 10.3 | Cover letter prompt + schema | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 10.4 | Cover letter generator | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 10.5 | CV improvement E2E test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 10.6 | Cover letter E2E test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

### Phase 11 — Credit System

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 11.1 | Credit ledger + balance tables | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 11.2 | Token metering middleware | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 11.3 | Tier definitions + enforcement | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 11.4 | Credit deduction on task completion | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 11.5 | Credit balance API + UI data | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 11.6 | Credit system E2E test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

### Phase 12 — Credit Purchasing

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 12.1 | Paddle account + product setup | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 12.2 | Paddle Checkout endpoint | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 12.3 | Paddle webhook handler | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 12.4 | Credit top-up logic + idempotency | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 12.5 | Credit purchase UI | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 12.6 | Paddle webhook E2E test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

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
| Scan CV against job | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| View ATS score + report | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Improve CV with AI | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Generate cover letter | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Download improved CV | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Download cover letter | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Buy credits with Paddle | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| View credit balance + history | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Browse visa-sponsored jobs | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Browse funded scholarships | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Generate SOP | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Generate research proposal | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
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
| ATS scan flow | tests/e2e/test_ats_scan_flow.py | — | ⏳ | — (not created) |
| CV improvement | tests/e2e/test_cv_improvement.py | — | ⏳ | — (not created) |
| Cover letter | tests/e2e/test_cover_letter.py | — | ⏳ | — (not created) |
| Credit system | tests/e2e/test_credit_system.py | — | ⏳ | — (not created) |
| Credit purchase | tests/e2e/test_credit_purchase.py | — | ⏳ | — (not created) |
| User onboarding | tests/e2e/test_user_onboarding.py | — | ⏳ | — (not created) |
| Full user journey | tests/e2e/test_full_journey.py | — | ⏳ | — (not created) |

> Unit tests (separate from E2E): 32 files / 326 passing / 93% engine
> line coverage (3289 statements, 225 missed). Verified via
> `python -m pytest --cov=engine`. Both `tests/e2e/` files run offline
> (MockTransport / network pinned dead) and are collected with the
> unit suite.

---
## 7. AUDIT FAILURES

Tasks marked complete in `state.json` but failing verification:

| Task | Claimed | Actual | Reason | Action |
|---|---|---|---|---|
| — | — | — | — | — |

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

---

## 11. NEXT SESSION ACTIONS

1. **Phase 4 — verification & hardening:** 4.1 domain verification (DNS + CNAME), 4.2 idempotency registry persistence, 4.3 cross-run SHA-256 hash chain, 4.4 circuit breaker + GitHub issue, 4.5 Supabase schema migration + RLS. (Phases 0–3 are closed: 32/88)
2. Then Phase 5 — product surface (CLI golden tests, web UI skeleton, SEO, waitlist) and Phase 6 — observability & deployment
3. 2.3 follow-up (carried): fold `FederalEmploymentAgency` into a government-sources registry so `adapters_for()` and the register dispatcher share one per-country source table (`docs/SOURCES.md` checklist step 2)
4. 2.8 follow-up (carried, new): `run_job_pipeline` loads by URL for W/G/L portals only — government sources are harvested through their adapters and need a detail loader before they are addressable by direct URL (documented in the `run_job_pipeline` docstring)
5. Registers: new published country register = **one data row** in `registers._REGISTER_SPECS` (+ status flip in `countries.py`); verify before claiming "live"
6. Push: retry when credentials allow (403 since session 3); all code/state/docs commits exist locally
7. LLM credentials: add at least one free-tier key to `.env` so 2.7's LLM polish path and the R17/R18/R24/R25/R26/R27/R28 gates can be exercised against a live provider — today they are verified with `MockTransport` / a scripted `_FakeClient` only

> Dependency note for Phase 11: `engine/credits/ledger.py` does not exist
> yet, so `handle_webhook()` records Paddle top-ups with status
> `ledger_pending` instead of crediting the balance. Acceptable until
> Phase 11 wires the ledger in (`topup_from_paddle`).

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
| No LLM API keys in this environment (no `.env`, all `.env.example` values are placeholders) | Every LLM call path runs dry-run only; live token / latency / 429 behaviour untested | Deterministic layers ship as the default path (2.7 falls back to it); add keys at launch prep and re-run the live-path tests |
| Pre-existing ruff/mypy debt in modules untouched this run (api.py, execute_step.py, retry.py, state_manager.py, test_execute_step.py) | Repo-wide lint/type gate not clean | ✅ **Cleared in run 6 (session 7):** `ruff check` + `ruff format --check` + `mypy` all pass on all 60 files. Nothing left to sweep |
| The other 49 European countries (all except GB) carry `sponsor_register="none"` (= *no known* public register, not *verified* absence — DE's "none" is the one documented fact among them) | Under-scored targeting if a country actually publishes one; wrong negative claim if it does not | The register layer already dispatches on the status (empty badge set, never a gate); when a register is discovered it's a one-row addition to `registers._REGISTER_SPECS` + a status flip in `countries.py` (session 7 follow-up, §11 item 5–6) |

