# BUILD BOARD — what I am working on right now, and what comes next

> Live working board for the continuous build loop. `PLATFORM_STATE.md` is the
> permanent record; this file is the *right now* view so you can always see
> what is in flight and what is queued.

**Session:** 12 — continuous loop to ship-ready
**After run 17:** 69/88 tasks complete (**78%**), run 17 closed (Phase 8 5/5), code `2b40f3c`
**Baseline suite:** 583 tests passing (60 files), 94% engine coverage (5409 stmts), `ruff` + `ruff format` + `mypy` clean repo-wide, **web `next build` EXIT=0**

---

## 0. SESSION-11 AUDIT — drift found & reconciled (done first)

| # | Finding | Resolution |
|---|---|---|
| 1 | Local `PLATFORM_STATE.md` edit had **reverted §3 rows for Phases 2–5** to ⏳ and deleted §10 sessions 1/2/5–9 — while §1/§2 claimed Phase 4 done | Restored from HEAD `6c7ccfd`, then applied the *verified* updates only |
| 2 | Local `state.json` claimed **5.1–5.4 complete** | 5.1/5.2 verified (`9775b07` + `tests/test_cli.py`); 5.3 verified (skeleton, adopted as `1efcae1`); **5.4 failed verification** (sitemap route only — no schema.org/JSON-LD, stock "Create Next App" metadata) → **reopened**, lands in run 19 |
| 3 | Commit `9775b07` (full CLI surface) was never recorded anywhere | 5.1/5.2 backfilled ✅ in state + §3 + §9 |
| 4 | Untracked `engine/ats/`: 9.1 parser + 9.3 keywords written but **untested**; 9.2 `scoring.py` had a **fatal SyntaxError** (broken `CATEGORY_WEIGHTS`) so `import engine.ats` failed — 381 green tests missed it because nothing imported it | ✅ **closed in run 13** — rebuilt, tested (93–99% cov), committed `ba616fa` |
| 5 | `run_manifest.json` ended at run 11 — **run 12 never appended** | Backfilled with the run-12 record |
| 6 | `CHANGELOG.md` stuck at Run 1; memory-bank carried stale 290/358 counts and "Session 10 / next Phase 5" | Backfilled runs 2–12 + audit entry; memory-bank rewritten |
| 7 | Baseline claimed "ruff + mypy clean" | True for the committed tree; red only on untracked `engine/ats/` (fix in run 13) |

Security: a GitHub classic token pasted in chat is treated as **compromised** —
it was never used and must be **rotated/revoked before any GitHub push**.

---

## 0.5. RUN 13 CLOSED — Phase 9 complete (2026-10-09)

| | |
|---|---|
| Tasks | 9.1–9.6 all ✅ — parser + 12-point rubric + keyword gaps + `POST /ats/score` + `GET /status` + `run_ats_scan` + offline E2E (`tests/e2e/test_ats_journey.py`) |
| Bugs found & fixed | `scoring.py` syntax (rebuilt), `_strings` unbound crash, MIME-hint format detection, extractor-error wrapping, stemmer `"es"` plural rule, `start_run()` return annotation, `domain.py` dnspython typing |
| Gates | 436 tests / 93% coverage / ruff + format + mypy green |
| Commits | `ba616fa` (code) → `d6f3287` (state); manifest run 13 appended |

---

## 0.6. RUN 14 CLOSED — Phase 10 complete (2026-10-09)

| | |
|---|---|
| Reconciled first | Board said 10.2/10.4/10.5/10.6 "queued", `PLATFORM_STATE.md` said Phase 10 0/6, `state.json` said pending — but the tree already had all six tasks. Suite run (462 green, gates clean) **before** anything was recorded |
| Tasks | 10.1–10.6 all ✅ — prompts/schemas audit-verified; `engine/improve/cv.py` (92% cov) fact-preserving edits; `engine/generators/cover.py` (96% cov) facts-only letters; `run_cv_improvement` + `run_cover_letter` wired; 2 offline E2E suites |
| Honesty notes | identity never model-owned (`original_cv_id`/`resume_id`/`job_id` re-stamped), summary counts recounted from shipped lists, JD keywords never invented without resume evidence |
| Gates | 462 tests / 4807 stmts @ 93% / ruff + format + mypy green |
| Commits | `1003b3e` (code) → state commit; manifest run 14 appended |

---

## 0.7. RUN 15 CLOSED — Phase 11 complete (2026-10-09)

| | |
|---|---|
| Tasks | 11.1–11.6 all ✅ — append-only idempotent ledger + `0002_credits.sql` balance tables; `CreditMeter` (pre-flight before work, charge on completion); free/pro/business tiers with once-per-month allowance; `user_id` metering wired on 9.5/10.2/10.4; `GET /credits/balance` + `/credits/estimate`; offline credit journey E2E |
| Notable | corrupt ledger fails **loudly** (`ledger_corrupt`, never resets balances); webhook's `ledger_pending` stub replaced with real `credited` behavior; no USD↔token rate invented — prices come from state only |
| Gates | 516 tests / 5120 stmts @ 93% (ledger 98, tiers 97, metering 100) / ruff + format + mypy green |
| Commits | `c1591d1` (code) → state commit; manifest run 15 appended |

---

## 0.8. RUN 16 CLOSED — Phase 12 complete (2026-10-10)

| | |
|---|---|
| Reconciled first | Board said run 16 queued; snapshot/state said Phase 12 0/6; manifest ended at run 15 — tree already held `e9146e9`. Gates re-run (540 green, 94% cov) **before** recording |
| Tasks | 12.1–12.6 all ✅ — PADDLE_SETUP audited + corrected (phantom `/api/*` paths → real routes, dashboard return URLs); `POST /credits/checkout` (honest 502 on missing keys); `POST /paddle/webhook` route; `0003_paddle.sql` closes the never-created `paddle_events` gap; `GET /credits/packs` + **purchase page with verified web build**; offline purchase E2E |
| Defects found & fixed | sitemap `export const dynamic` vs `cacheComponents` (pre-existing 5.3 defect, first-ever web build); dead `success_url`/`cancel_url` client params; documented-but-unread `VANTIA_*_TIER_TOKENS` env vars (now real overlays) |
| Gates | 540 tests / 5177 stmts @ 94% / ruff + format + mypy green / `next build` EXIT=0 |
| Commits | `e9146e9` (code) → state commit; manifest run 16 appended |

---

## 0.9. RUN 17 CLOSED — Phase 8 complete (2026-10-10)

| | |
|---|---|
| Tasks | 8.1–8.5 all ✅ — offline HS256 JWT verify + refresh (`engine/auth/`, 98% cov); `0004_workspaces.sql` profiles/workspaces/files (tier parity-tested vs engine TIERS); `0005_rls.sql` 12 `auth.uid()` policies + hardened `vantia_jwt_hook`; `WorkspaceStorage` (user-scoped paths, validate-before-network, honest codes); two-user isolation E2E with zero-storage-call refusal |
| Defects found | PyJWT imported but never declared → added to requirements/pyproject; `SupabaseClient` lacked `delete()` (added); fake-client filter unpacking bug in tests caught by first run |
| Honest limits | migrations 0004/0005 written + static-tested, **not applied** (no live Postgres); dashboard hook registration documented as launch step |
| Gates | 583 tests / 5409 stmts @ 94% / ruff + format + mypy green |
| Commits | `2b40f3c` (code) → state commit; manifest run 17 appended |

---

## 1. CURRENTLY IN FLIGHT

**Run 18 — Phase 6: Observability & Deployment** (6.1 → 6.7)

| # | Task | Status |
|---|---|---|
| 6.1 | Structured logging (run_id, hashes) | **in flight** — audit `engine/logging_config.py` against the task; add run_id/hash fields where missing |
| 6.2 | Public status page | queued — `/status` exists (9.4); build the public page/route on top |
| 6.3 | Docker + reproducibility | **audit** — `Dockerfile` exists from Phase 0; verify pins/reproducibility, fill gaps |
| 6.4 | Render deployment config | queued — `render.yaml` |
| 6.5 | Vercel deployment config | queued — `vercel.json` for `web/` |
| 6.6 | Supabase setup guide + SQL migration | queued — migration rollout doc for 0001–0005 |
| 6.7 | Keep-alive documentation | **audit** — workflows + RUNBOOK exist; verify + record |

Honest limit (unchanged): no Render/Vercel/Supabase credentials — configs
are validated structurally (YAML/JSON parse, schema checks, docs review),
never claimed as deployed.

Design rules carried from the existing generators (2.7, 3.2, 3.3):

1. **Deterministic first** — the ship layer runs with no provider, no key,
   no network. The LLM is an accelerator, never a dependency.
2. **Schema-valid on every path** — the payload is validated against
   `engine/schemas/ats_score.schema.json` before it is returned.
3. **Honest degradation** — PDF/DOCX extraction degrades loudly
   (`extraction_confidence="partial"`) instead of silently returning an
   empty resume; an unparseable upload raises rather than guessing.
4. **Never invent** — missing contact details or experience show up as
   explicit gaps in the report instead of being filled with plausible text.

---

## 2. QUEUE (each run: code + tests → suite/lint green → state + all `.md` → commit)

| Run | Phase | Tasks | Notes |
|---|---|---|---|
| 19 | 5 — Product Surface closeout | 5.4, 5.5, 5.6 | **5.4 reopened by audit**; 6 SEO landing pages + waitlist double opt-in; verify `web/` builds |
| 20 | 13 — Workspace UI + Full Journey | 13.1–13.6 | the user-facing surface |
| 21 | 7 — Acceptance | 7.1–7.3 | full E2E, failover, paid-model switching |

---

## 3. HONEST LIMITS OF THIS ENVIRONMENT (no change, tracked)

* No Supabase / Render / Vercel / Paddle credentials — all are
  `REPLACE_ME` placeholders. SQL migrations are **written and
  static-tested**, not applied. Nothing claims a migration was pushed.
* No LLM API keys — every provider path is verified with `MockTransport`
  / a scripted fake client only. Dry-run stays deterministic.
* No `gh` CLI — incident issues fall back to the offline Markdown draft
  path in `.vantia/issues/`.
* Supabase-backed code is tested against an in-memory fake client, so the
  logic is proven even though no network call succeeds.
* Push to origin: **done** (2026-10-10, `6c7ccfd..8ef642e`) using the
  disclosed classic token under explicit user authorization; the user will
  rotate it at 100% build. Until rotation, treat the token as compromised:
  it is used only as an inline `oauth2:` URL and never written to the repo.
