# Vantia — Architecture (v4.0)

## Trust model

Everything runs on free-tier infrastructure. **Supabase is a write-through
mirror; git is authoritative.** If Supabase is down, the run continues and
the state mirror lives in `.vantia/` committed to the `vantia-state` branch.

| Branch | Contents |
|--------|----------|
| `main` | Code, tests, workflows, docs, `.vantia/mirror.json` |
| `vantia-state` | Authoritative `.vantia/state/state.json`, artifacts, hash chain, cost ledger, idempotency registry |

`.vantia/` is gitignored on `main`; it is force-added on `vantia-state`.

## Layers

1. **Orchestration** — `engine/state_manager.py`, `engine/execute_step.py`.
   Resolves dependencies, drives the task lifecycle, owns all commits.
2. **Audit** — `engine/hash_chain.py` (SHA-256 chain),
   `engine/cost_tracker.py` (JSONL ledger), `engine/idempotency.py`.
3. **State** — `engine/state_manager.py` + `engine/locking.py`
   (30-minute stale-lock steal).
4. **Persistence** — `engine/persistence/supabase_client.py` (httpx REST,
   degrades to a warning) + `engine/persistence/fallback.py` (git mirror).
5. **LLM** — provider registry (`engine/llm/providers.yaml`, Phase 1),
   router with multi-provider failover, fence stripper, quota gate.
6. **Pipelines** — `engine/pipeline.py` (job, scholarship, ATS scan,
   CV improvement, cover letter).
7. **API** — `engine/api.py` (`/health` + self-ping startup hook),
   `engine/keep_alive.py`.
8. **CLI** — `engine/cli.py` (`vantia init|status`, expanded in Phase 5).

## Subsystems added in v4.0

- `engine/auth/`       — Supabase auth JWT extraction + refresh
- `engine/workspace/`  — workspace RLS + Supabase Storage
- `engine/ats/`        — resume parser, 12-point scorer, keyword matcher
- `engine/improve/`    — CV improver + cover letter generator
- `engine/credits/`    — credit ledger, token metering, tiers, Paddle

## Runtime files (`.vantia/`)

| File | Purpose |
|------|---------|
| `state/state.json` | Authoritative run state (14 phases, 88 tasks) |
| `state/state.lock` | Run lock; stolen after 30 min of staleness |
| `master_version` | `4.0` |
| `hash_chain.json` | Cross-run SHA-256 chain |
| `costs.jsonl` | One line per LLM call |
| `idempotency_registry.json` | task id → artifacts |
| `mirror.json` | Latest git fallback snapshot |
| `artifacts/` | Artifacts committed on `vantia-state` |
