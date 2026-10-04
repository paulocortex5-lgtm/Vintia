# VANTIA — PLATFORM STATE

**Last updated:** 2026-10-04T08:03:45Z
**Master prompt:** v6.0
**Session count:** 3
**Overall readiness:** 13%

---

## 1. SHIPPING READINESS SUMMARY

| Metric | Value |
|---|---|
| Tasks complete | 12/88 |
| Tasks in progress | 0 |
| Tasks blocked | 0 |
| Tasks pending | 76 |
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
| 1 | Schemas + Prompts + LLM Router | 3/7 | 0 | 0 | 4 | 43% |
| 2 | Jobs Trail | 0/9 | 0 | 0 | 9 | 0% |
| 3 | Scholarship Engine | 0/7 | 0 | 0 | 7 | 0% |
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
| 1.1 | Envelope + ATS schema | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 1.2 | SOP schema | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 1.3 | Research proposal schema | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 1.4 | Prompt templates v1 | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 1.5 | LLM provider registry (providers.yaml) | ✅ Complete | `279c3ca` | engine/llm/providers.yaml (22 providers: 12 free / 10 paid), engine/llm/router.py, engine/llm/__init__.py, tests/test_llm_router.py | ✅ | ❌ | ✅ |
| 1.6 | LLM router + multi-provider failover | ✅ Complete | `279c3ca` | engine/llm/quota.py, tests/test_quota.py | ✅ | ❌ | ✅ |
| 1.7 | LLM client + fence stripper + quota | ✅ Complete | `279c3ca` | engine/llm/client.py, engine/json_utils.py, engine/llm/__init__.py, tests/test_llm_client.py, tests/test_json_utils.py | ✅ | ❌ | ✅ |

### Phase 2 — Jobs Trail

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 2.1 | Fetch base + robots.txt + rate limit | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 2.2 | Portal adapters (W/G/L) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 2.3 | Visa register fetchers (UK/DE/AU) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 2.4 | Credential equivalence lookup | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 2.5 | Fraud filter (domain/fee/middleman) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 2.6 | Injection + PII redactor | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 2.7 | ATS resume generator | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 2.8 | pipeline.py: run_job_pipeline | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 2.9 | E2E job pipeline test | ⏳ Pending | — | — | ❌ | ❌ | ❌ |

### Phase 3 — Scholarship Engine

| ID | Name | Status | Commit | Files | Tested | Previewed | Verified |
|---|---|---|---|---|---|---|---|
| 3.1 | Scholarship database (5 programs) | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 3.2 | SOP generator | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 3.3 | Research proposal generator | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 3.4 | Academic credential mapper | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
| 3.5 | Application window tracker | ⏳ Pending | — | — | ❌ | ❌ | ❌ |
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
| Check credential equivalence | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Fraud filter blocks scams | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

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
| Job pipeline | tests/e2e/test_job_pipeline.py | — | ⏳ | — (not created) |
| Scholarship pipeline | tests/e2e/test_scholarship_pipeline.py | — | ⏳ | — (not created) |
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

> Unit tests (separate from E2E): 18 files / 165 passing / 91% engine
> line coverage (1420 statements, 123 missed). Verified via
> `python -m pytest --cov=engine -q`.

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

> ⏳ **Push blocked this session.** The environment's cached GitHub
> credential belongs to an account without access to
> `paulocortex5-lgtm/Vintia` (HTTP 403, no `gh` CLI, no stored token).
> Both commits exist locally and are ready to push with the inline
> credential documented in `docs/RUNBOOK.md`:
>
> ```bash
> git push https://oauth2:<token>@github.com/paulocortex5-lgtm/Vintia.git main
> git push https://oauth2:<token>@github.com/paulocortex5-lgtm/Vintia.git vantia-state
> ```

---

## 10. SESSION LOG

### Session 3 — 2026-10-04 — Phase 1 LLM stack (1.5/1.6/1.7) + Stripe→Paddle purge (task 0.0)

| Item | Outcome |
|---|---|
| 1.5 `providers.yaml` | 22 providers (12 free / 10 paid) with openai / gemini / anthropic / cohere payload styles; add a provider = edit YAML only (R38) |
| 1.6 router + quota | `pick()` free-before-paid chain (R27), skips providers without keys or with exhausted quota; `QuotaTracker` daily rollover, rpd/rpm caps, optional Supabase `llm_usage` mirror |
| 1.7 client + json_utils | `LLMClient.complete()` / `run_chain()` failover (429 → next provider), dry-run with zero network I/O (R25), `VANTIA_MAX_COST_USD` ceiling (R18), hash-chained envelope (R24); `strip_fences`, `canonical_json`, `safe_parse` |
| 0.0 Stripe → Paddle | Every `STRIPE_*` reference removed repo-wide; added `PaddleError`, `paddle_client` (checkout transactions), `paddle_webhook` (HMAC-SHA256 + 5 s replay window + `paddle_events` idempotency), `docs/PADDLE_SETUP.md` |
| Bug found & fixed | `QuotaTracker.usage_snapshot()` held a non-reentrant `threading.Lock` while calling `remaining_rpd()` / `check_quota()`, which re-acquire it → deadlock that hung the test run. Switched to `threading.RLock` |
| Tests | 18 files / 165 passing / 91% `engine/` line coverage (`pytest --cov=engine -q`) |
| Lint & types | All new + touched files: `ruff check` clean, `ruff format --check` clean. Repo-wide debt in untouched modules is tracked in §12 |
| Push | ❌ blocked (403 — cached credential lacks access to `paulocortex5-lgtm/Vintia`); commits `279c3ca` (main) and `76867be` (vantia-state) are ready locally — see §9 |

_(Earlier sessions populated above during Phase 0.)_

---

## 11. NEXT SESSION ACTIONS

1. 1.1 — Envelope + ATS schema (`engine/schemas/`)
2. 1.2 — SOP schema
3. 1.3 — Research proposal schema
4. 1.4 — Prompt templates v1 (`engine/prompts/v1_*.md`)

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
| Master prompt header says 98 tasks, catalog lists 88 | Progress denominator confusion | state.json + catalog agree on 88; use 88 |
| Provider/infra credentials are REPLACE_ME placeholders | Network-success paths untested | Insert real keys during launch prep |
| Pre-existing ruff/mypy debt in modules untouched this run (api.py, execute_step.py, retry.py, state_manager.py, test_execute_step.py) | Repo-wide lint/type gate not clean | New code passes `ruff check` + `ruff format --check`; sweep alongside Phase 4 hardening |

