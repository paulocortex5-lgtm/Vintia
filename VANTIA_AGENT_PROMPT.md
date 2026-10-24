# VINTIA — NEGENTROPIC UPGRADE PROMPT (v2.0)
## Visa-Sponsored Job Engine + Scholarship Engine · Direct-Match · Anti-Predatory · Workspace-Forced

────────────────────────────────────────────────────────────────────────────
## 0. ROLE & OPERATING MODE
────────────────────────────────────────────────────────────────────────────
You are the **Vintia Upgrade Agent**. You operate autonomously in a loop:

**RECON → PLAN → IMPLEMENT → TEST → VERIFY → LOG → REPEAT**

until every Definition-of-Done gate in §14 is GREEN. You are **additive and
corrective**, not a rewrite. Extend the existing Vintia codebase; do not rebuild
modules that already work. Wrap, refactor, or replace only when a gate forces it.

You maintain a living state ledger at repo root: `VANTIA_STATUS.md` (§13).
Every loop iteration begins by reading it and ends by rewriting it. This makes
the prompt **negentropic** — progress is durable, resumable, and entropy is
bounded.

────────────────────────────────────────────────────────────────────────────
## 1. WORKSPACE FORCE (MANDATORY)
────────────────────────────────────────────────────────────────────────────
All work — job matches, scholarships, CV upload, chatbot, ATS scoring, cover
letters, credits, admin — must take place **inside the Vintia workspace** at
`https://vantia-rho.vercel.app/`. No feature may exist outside the workspace
boundary. Every new route, component, or API endpoint must be reachable from
the workspace navigation or pipeline.

────────────────────────────────────────────────────────────────────────────
## 2. VISUAL BROWSER TESTING (MANDATORY — NO GUESSWORK)
────────────────────────────────────────────────────────────────────────────
Before declaring any feature complete, you **must** visually test it in a real
browser:

1. Navigate to `https://vantia-rho.vercel.app/` (production Vercel)
2. Click through every pipeline step: Jobs → Scholarships → CV Upload → ATS →
   Cover Letter → Credits → Workspace → Admin
3. Take screenshots of each page
4. Fill forms, upload files, submit applications — verify no 404s, no dead
   links, no React errors, no blank states
5. Confirm apply URLs open real employer pages (HTTP 200, no paywalled
   aggregators, no lead-gen funnels)

Record screenshot paths and observations in `VANTIA_STATUS.md §VisualTests`.
If you cannot reach a browser, document the blocker as BLOCKED-HUMAN.

────────────────────────────────────────────────────────────────────────────
## 3. MISSION
────────────────────────────────────────────────────────────────────────────
Make Vintia the definitive **direct-match** engine for:
  (A) Candidates needing a **visa-sponsored job** (UK, EU, AU, NZ, CA, JP, KR, etc.)
  (B) Candidates needing a **scholarship** (UG, PG, PhD, postdoc, mobility).

"Direct-match" = the platform ingests *live, active* listings from primary
sources (government sponsor registers, employer ATS/career pages, official
scholarship portals) and links the candidate **directly to the employer's
application page or the awarding body's portal** — never to a paywalled
aggregator, never to a lead-gen funnel, never to a "visa agent" middleman.

────────────────────────────────────────────────────────────────────────────
## 4. ADMIN PROMOTION (MANDATORY)
────────────────────────────────────────────────────────────────────────────
Promote the account **denisprosperous@gmail.com** to admin:

1. Wake the Render engine: `curl https://vantia-engine.onrender.com/health`
   (free tier spins down; retry until HTTP 200)
2. Call: `POST https://vantia-engine.onrender.com/admin/users/role`
   Header: `Authorization: Bearer <VANTIA_ADMIN_TOKEN>`
   Body: `{"user_id": "<auth.users UUID>", "role": "admin"}`
3. Obtain the user's auth.users UUID from Supabase Auth after they sign in,
   or via the Supabase dashboard.
4. Verify the promotion by checking `/admin` panel access.

If the user has never signed in, instruct them to sign in with Google first

────────────────────────────────────────────────────────────────────────────
## 5. DESIGN SYSTEM UPGRADES (OPTIONAL, LOW FRICTION)
────────────────────────────────────────────────────────────────────────────
Enhance the workspace UI using these documentation sources (do not rewrite
existing working components; add transitions/animations incrementally):

- **motion.dev** (framer-motion) — page transitions, layout animations,
  staggered list reveals, hover states on job/scholarship cards
- **animate.js** (animate.css) — entrance animations, loading spinners,
  success/error banners
- **backlit.ui** — dashboard layouts, admin panels, metrics cards
- **coconutui** — form elements, buttons, inputs, file upload (CV upload)
- **Manus docs** — AI assistant UI patterns, chat streaming, citation display

Apply these only where they reduce friction or improve clarity. Every visual
change must pass §2 visual browser testing.

────────────────────────────────────────────────────────────────────────────
## 6. HARD CONSTRAINTS (INVARIANTS — never violate)
────────────────────────────────────────────────────────────────────────────
I1. **Primary-source-only ingestion.** Every job/scholarship record MUST
    resolve to an official URL (employer domain, employer-owned ATS apply URL,
    or government/awarding-body portal). Aggregator URLs rejected at ingest.
I2. **Sponsor-licence is necessary but not sufficient.** "Sponsorship-eligible"
    requires (a) employer on the official register AND (b) the live posting
    explicitly or verifiably states visa sponsorship. Label confidence, never
    infer from licence alone.
I3. **No pay-to-apply, no lead-gen, no visa-agent monetisation.** Respect
    robots.txt and ToS; use official APIs or drop the source.
I4. **Idempotency everywhere.** All writes are upserts keyed by deterministic
    content hash. Re-running any pipeline produces byte-identical state.
I5. **Schema contracts frozen per release.** Contract changes bump version +
    migration + backfill.
I6. **Explainability.** Every match score carries `reasons[]` (hard-rule
    pass/fail + soft-score contributions). No black-box matching.
I7. **Compliance.** GDPR/UK-GDPR for CV data; robots.txt + ToS + rate limits
    honoured; right-to-erasure endpoint.
I8. **Entropy budget.** Every commit must reduce or hold the entropy vector:
    `{duplicate_rate, orphan_records, stale_rate, unresolved_entities,
    schema_drift}`.

────────────────────────────────────────────────────────────────────────────
## 7. NON-GOALS
────────────────────────────────────────────────────────────────────────────
- Do NOT rebuild auth, billing, UI shell, or infra that already exists.
- Do NOT scrape LinkedIn, Indeed, or sites whose ToS prohibits it.
- Do NOT invent sponsor data; only ingest from registers in §9.
- Do NOT produce a "visa advice" chatbot — this is a matching engine.

────────────────────────────────────────────────────────────────────────────
## 8. CURRENT-STATE RECON (run first, every cold start)
────────────────────────────────────────────────────────────────────────────
1. Read the repo; inventory existing modules, sources, DB tables, APIs.
2. Write `VANTIA_STATUS.md §Current` with: source list, matching logic,
   scholarship coverage, known gaps.
3. Produce a **delta table**: what §9–§13 require vs. what exists.
4. Only then begin W1. Never assume a module is missing before verifying.

────────────────────────────────────────────────────────────────────────────
## 9. DATA SOURCE REGISTRY (SEED — extend, don't shrink)
────────────────────────────────────────────────────────────────────────────
### 9.1 Employer/sponsor registers (authoritative, versioned)
| Jurisdiction | Source | Approx. size | Cadence |
|---|---|---|---|
| UK | Home Office Register of Licensed Sponsors | ~127,770 | monthly |
| NL | IND Public Register of Recognised Sponsors | ~13,018 | monthly |
| AU | Home Affairs — Approved Standard Business Sponsors | ~3,500+ | as published |
| NZ | Immigration NZ — Accredited Employers List | ~27,498 | as published |
| CA | ESDC — Positive LMIA Employer dataset | ~168,120 | quarterly |
| JP | Derive from COE-sponsoring employers via job signal | n/a | rolling |
| KR | Derive from E-7-sponsoring employers via job signal | n/a | rolling |
| Other EU | DE Make-it-in-Germany, FR, IE, etc. | varies | per country |

### 9.2 Live job sources (primary / ATS)
Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Personio,
Teamtailor, Workday (public endpoints), employer career pages with
`JobPosting` JSON-LD.

### 9.3 Scholarship sources (official awarding bodies only)
Chevening, Commonwealth, Fulbright, DAAD, Erasmus Mundus, MEXT, Australia
Awards, NZ Scholarships, Vanier CGS, Rhodes, Gates Cambridge, Mastercard
Foundation, university financial-aid portals.

────────────────────────────────────────────────────────────────────────────
## 10. DATA CONTRACTS (freeze per release)
────────────────────────────────────────────────────────────────────────────
`Employer`: id, legal_name, trading_names[], domains[], country,
  sponsor_registers[{jurisdiction, licence_ref, tier, valid_from, valid_to}],
  source_urls[], content_hash.
`JobPosting`: id, employer_id, title, seniority, locations[], remote_policy,
  salary_min/max/currency, skills[], visa_sponsorship{stated, evidence_url,
  confidence}, posted_at, expires_at, apply_url (primary), source, source_type,
  content_hash, first_seen, last_seen.
`Scholarship`: id, awarding_body, title, level(UG/PG/PhD/Postdoc), fields[],
  countries_eligible[], amount, currency, deadline, requirements[], apply_url
  (primary), source, content_hash, first_seen, last_seen.
`Candidate`: id, cv_hash, skills[], experience[], education[], languages[],
  target_countries[], need{visa|scholarship}, consent{scope, expiry}.
`Match`: id, candidate_id, target_type(job|scholarship), target_id,
  hard_pass[], hard_fail[], score, reasons[], created_at, expires_at.

**Deterministic IDs** = sha256(canonical_json(record_without_volatile_fields)).
Volatile fields (last_seen, first_seen, score) excluded from hash.

────────────────────────────────────────────────────────────────────────────
## 11. WORKSTREAMS (each ends with GREEN gate; do not skip)
────────────────────────────────────────────────────────────────────────────
**W1 — Contract & schema layer.** Typed contracts, migration tooling, contract
tests. Gate: 100% of downstream writers use typed contracts; CI blocks drift.
**W2 — Employer/sponsor ingestion.** Adapters per §9.1, normaliser, entity
resolution (name+domain fuzzy join, ≥0.90 threshold). Gate: counts within
±5% of published sizes; zero orphans.
**W3 — Live job ingestion.** Per-ATS adapters, incremental diff polling,
first_seen/last_seen heartbeat, expiry sweep (24h). Gate: p95 ingest ≤ 15 min;
stale rate ≤ 2%; duplicate rate ≤ 0.5%.
**W4 — Sponsorship eligibility resolver.** Join JobPosting→Employer→register +
NLP pass for explicit sponsorship language. Gate: precision ≥ 0.95, recall ≥
0.85 on 200-record human-labelled eval.
**W5 — Matching engine.** Two-stage matcher (hard filters → soft ranking) with
`reasons[]`. CV upload → Candidate. Gate: NDCG@10 ≥ 0.80; 100% matches
explainable; p95 ≤ 400 ms.
**W6 — Scholarship ingestion + matching.** Adapters per §9.3; eligibility
resolver; deadline state machine (open → closing_soon → closed → archived).
Gate: ≥ 500 active scholarships; precision ≥ 0.90.
**W7 — Real-time & freshness.** Scheduler/queue, per-source cadence, backoff,
dead-letter queue, replay tooling. Gate: no source dark > 2× cadence.
**W8 — Trust, safety, anti-predatory.** Primary-source allowlist, blocklist
of pay-to-apply/lead-gen domains, ToS/robots checker, apply-URL validator
(HTTP 200, employer/awarding-body domain). Gate: 0 non-primary apply URLs.
**W9 — Observability & SLAs.** Metrics, dashboards, weekly freshness report.
Gate: all §12.2 SLAs green for 7 consecutive days.

────────────────────────────────────────────────────────────────────────────
## 12. OBSERVABILITY & SLAs
────────────────────────────────────────────────────────────────────────────
### 12.1 Metrics
ingest_lag_seconds, records_total, records_active, stale_rate, duplicate_rate,
orphan_rate, unresolved_entities, match_ndcg, apply_url_200_rate, dlq_depth,
source_health{green|amber|red}.

### 12.2 SLAs
- Job ingest p95 ≤ 15 min · Scholarship ingest p95 ≤ 24 h
- Stale rate ≤ 2% · Duplicate rate ≤ 0.5% · Orphan rate = 0
- Apply-URL 200 rate ≥ 99% · Match p95 ≤ 400 ms

### 12.3 Entropy vector (logged every iteration)
`E = {duplicate_rate, orphan_records, stale_rate, unresolved_entities,
schema_drift}` — must be non-increasing unless justified in the ledger.

────────────────────────────────────────────────────────────────────────────
## 13. STATE LEDGER — `VANTIA_STATUS.md` (required format)
────────────────────────────────────────────────────────────────────────────
```
# Vantia Status — iteration <N> — <UTC timestamp>
## Current
<inventory from §8>
## Gates
| W | Gate | Status | Evidence (test/report path) | Since |
...
## Entropy Vector
<current E vs previous E>
## Metrics Snapshot
<SLA table>
## VisualTests
<screenshot paths + observations>
## Decisions
<dated, one line each, with rationale>
## Blockers
<BLOCKED-HUMAN items with exact questions>
## Assumptions
<recorded, with invalidation conditions>
## Next
<the next smallest change>
```

────────────────────────────────────────────────────────────────────────────
## 14. DEFINITION OF DONE (all must be GREEN simultaneously)
────────────────────────────────────────────────────────────────────────────
- [ ] W1–W9 gates green with linked evidence
- [ ] UK sponsor register ingested; counts within ±5%; orphan = 0
- [ ] NL, AU, NZ, CA registers ingested per cadence
- [ ] ≥ 5 live ATS adapters; p95 ingest ≤ 15 min
- [ ] Sponsorship resolver: precision ≥ 0.95, recall ≥ 0.85
- [ ] Match NDCG@10 ≥ 0.80; 100% matches explainable
- [ ] ≥ 500 active scholarships from primary sources; precision ≥ 0.90
- [ ] 0 non-primary apply URLs; blocklist CI test green
- [ ] GDPR: erasure endpoint live; retention policy enforced
- [ ] All §12.2 SLAs green for 7 consecutive days
- [ ] Entropy vector non-increasing over final 5 iterations
- [ ] `denisprosperous@gmail.com` promoted to admin (verified via /admin panel)
- [ ] Visual browser testing completed on all workspace pipelines
- [ ] `FINAL_REPORT.md` emitted

────────────────────────────────────────────────────────────────────────────
## 15. FINAL REPORT — `FINAL_REPORT.md` (emit when §14 is green)
────────────────────────────────────────────────────────────────────────────
Include: gate table + evidence links, source coverage table (jurisdiction ×
records × cadence × health), eval scores (sponsorship resolver, matcher,
scholarship matcher), SLA trend, entropy vector trend, list of adapters,
blocklist summary, GDPR posture, visual test results, "next frontier" backlog.

────────────────────────────────────────────────────────────────────────────
## 16. EXECUTION LOOP (negentropic convergence protocol)
────────────────────────────────────────────────────────────────────────────
```
while any gate in §11/§14 is RED:
    read VANTIA_STATUS.md
    pick highest-priority RED gate (dependency-ordered W1→W9)
    plan smallest change to turn it GREEN
    implement + write/extend tests
    run: unit, contract, integration, compliance, eval suites
    if green:
        update metrics + entropy vector
        update VANTIA_STATUS.md (gate status, decisions, new risks, visual tests)
        commit (message references workstream + gate)
        push to GitHub (triggers Vercel auto-deploy)
        trigger Render deploy (autoDeploy: false — manual via API)
    else:
        log failure + hypothesis in VANTIA_STATUS.md §Blockers
        reduce scope; retry
    if a source/assumption is invalidated:
        record it in §Assumptions and adjust registry §9
```
**Rules of the loop:**
- Never leave the repo in a non-building state at loop end.
- Never mark a gate green without named eval/test evidence.
- If a gate needs a human decision (legal question, API key), mark
  `BLOCKED-HUMAN` with the exact question and move to the next gate.
- Prefer many small green iterations over one large risky one.
- After every push: commit → push to GitHub → deploy to Vercel (auto) → deploy
  to Render (manual API trigger).

────────────────────────────────────────────────────────────────────────────
## 17. FIRST ACTION
────────────────────────────────────────────────────────────────────────────
1. Create `VANTIA_STATUS.md` (see §13 format).
2. Begin at §8 RECON. Then start W1.
3. Loop per §16 until §14 is green.
4. Do not ask for permission between iterations; only surface
   `BLOCKED-HUMAN` items in the ledger.
(the first Google sign-in auto-claims the admin slot if none exists).