# `.vantia/` — Vantia Runtime State

This directory holds **runtime state only**. It is gitignored on
`main` and tracked on the orphan branch `vantia-state`.

Never commit this directory to `main`: runtime state must not ship in a
deployment.

## Contents

| Path | Purpose |
|---|---|
| `master_version` | Master prompt version gate; must read `4.0` |
| `state/state.json` | Authoritative task/run state (the source of truth) |
| `state/state.lock` | File lock for atomic state writes |
| `artifacts/` | LLM-generated artifact envelopes (ats/, sop/, proposals/, cover_letters/, cv_improvements/) |
| `cache/fetches/` | Fetch cache with 7-day TTL |
| `cache/llm/` | LLM response cache |
| `cache/dns/` | DNS/CNAME lookup cache |
| `quarantine/` | Blocked content (fees/, injection/, domain/) |
| `hash_chain.json` | Cross-run SHA-256 integrity chain |
| `idempotency_registry.json` | Idempotency key → artifact path |
| `costs.jsonl` | One line per LLM call |
| `rate_limits.json` | Per-host 1 req/sec rate-limit state |
| `mirror.json` | Latest git fallback snapshot |
| `run_manifest.json` | Human-readable summary of each build run |

## Recovery

```bash
git checkout vantia-state -- .vantia/state/state.json
```

## Fail-safe invariants

- **Corrupt lock file** → refused, left untouched (never stolen).
- **Corrupt state / registry file** → fails loudly (never silently repaired).

Both are deliberate: git is the authoritative audit trail, so refusing
to proceed is always safer than guessing.