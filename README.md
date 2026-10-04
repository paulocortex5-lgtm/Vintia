# Vantia — Universal Opportunity Engine

Vantia is an AI-powered workflow engine that replaces predatory job boards and
recruitment agencies with a direct, verified pipeline for:

1. International job applications with visa-sponsorship filtering
2. Fully funded scholarship matching and Statement of Purpose generation
3. Research proposal generation for MRes/PhD funding
4. Credential equivalence translation (NVQ, HND, BTS, CAP, GPA ↔ ECTS, etc.)
5. Anti-fraud guardrails that block fee-charging middlemen
6. ATS resume scoring against job descriptions
7. AI-powered CV improvement with targeted rewriting
8. Cover letter generation aligned to job postings
9. Per-user workspaces with private storage and isolated data
10. Token-based credit system with tier enforcement
11. Credit purchasing via Paddle Billing (sandbox at launch)

> **Product promise:** *Every application Vantia produces is targeted, verified,
> and free of third-party intermediaries.*

## Quickstart

```bash
pip install -e .
vantia init
vantia apply --job https://boards.greenhouse.io/... --resume me.pdf \
      --country GB --visa "Skilled Worker"
```

## Architecture (high level)

```
Engine ─┬─ Jobs Trail ─────────────┐
        ├─ Scholarship Engine ─────┤
        └─ AI Prep & Verification ─┤
                                   ▼
                        User Workspace Layer (Supabase RLS)
                                   ▼
                        LLM Router (free-first, paid opt-in)
                                   ▼
                        Persistence (Supabase + git audit trail)
                                   ▼
                        Deployment (Render + Vercel + Supabase, $0/mo)
```

## Repository layout

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Runtime state is
authoritative on the `vantia-state` branch; the engine mirrors it to Supabase.

## Status

Built incrementally across sessions. See [`CHANGELOG.md`](CHANGELOG.md) and
`.vantia/state/state.json` (on the `vantia-state` branch) for live progress.

## License

MIT — see [`LICENSE`](LICENSE).
