# BUILD BOARD — what I am working on right now, and what comes next

> Live working board for the continuous build loop. `PLATFORM_STATE.md` is the
> permanent record; this file is the *right now* view so you can always see
> what is in flight and what is queued.

**Session:** 11 — audit → continuous loop to ship-ready
**After run 13:** 46/88 tasks complete (**52%**), run 13 closed, HEAD `d6f3287`
**Baseline suite:** 436 tests passing (42 files), 93% engine coverage, `ruff` + `ruff format` + `mypy` clean repo-wide

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

## 1. CURRENTLY IN FLIGHT

**Run 14 — Phase 10: CV Improvement + Cover Letter** (10.1 → 10.6)

| # | Task | Status |
|---|---|---|
| 10.1 | CV improvement prompt + schema | **audit-verified** — `v1_cv_improve.md` + `cv_improvement.schema.json` exist and are tested (`tests/test_prompts.py`, `tests/test_schemas.py`) → record ✅ |
| 10.2 | CV improvement engine | queued — deterministic-first on the 2.7/3.2 pattern (`engine/improve/`) |
| 10.3 | Cover letter prompt + schema | **audit-verified** — `v1_cover_letter.md` + `cover_letter.schema.json` exist and are tested → record ✅ |
| 10.4 | Cover letter generator | queued — `run_cover_letter` stub raises until wired |
| 10.5 | CV improvement E2E | queued |
| 10.6 | Cover letter E2E test | queued |

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
| 15 | 11 — Credit System | 11.1–11.6 | `ledger.py` is the missing dependency named in §11 of PLATFORM_STATE |
| 16 | 12 — Credit Purchasing | 12.1, 12.2, 12.4, 12.5, 12.6 | **audit:** 12.3 webhook exists + tested; 12.2 client exists but untested; 12.1 doc exists (PADDLE_SETUP) — verify + fill gaps |
| 17 | 8 — User Workspaces | 8.1–8.5 | SQL migrations + storage + isolation E2E |
| 18 | 6 — Observability & Deployment | 6.1–6.7 | render.yaml, vercel, status page, docs |
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
* Push to origin stays local-only until the disclosed classic token is
  rotated (see §0).
