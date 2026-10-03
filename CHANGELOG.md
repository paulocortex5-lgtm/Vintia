# Changelog

All notable changes to Vantia are recorded here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/). Every engine task appends an
entry in the form `vantia(<task_id>): <name> (run N)`.

## [Unreleased]

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
