# Vantia Runbook

Operational runbook for the Vantia engine. Covers the local developer
loop, the three-layer keep-alive, deployment, recovery, and rollback.

> Scope: this runbook covers **Phase 0** concerns (scaffold, CI,
> keep-alive, recovery). Phase 6 adds the deployment runbooks
> (`RENDER_DEPLOY.md`, `VERCEL_DEPLOY.md`, `SUPABASE_SETUP.md`,
> `KEEP_ALIVE.md`) and the Paddle runbook.

---

## 1. Local development loop

```bash
# 1. Clone
git clone https://github.com/paulocortex5-lgtm/Vintia.git
cd Vintia

# 2. Virtual environment + install
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt

# 3. Configure
cp .env.example .env.local      # then fill in the REPLACE_ME values

# 4. Bootstrap the runtime state
./bootstrap.sh

# 5. Verify
python -c "import engine" && echo OK
python -m pytest --cov=engine -q
```

`bootstrap.sh` is idempotent: it creates the `.vantia/` tree, seeds
`.vantia/state/state.json` from `engine/seed/state.json`, and creates
the artifact/quarantine/cache directories. Re-running it never
overwrites existing state.

### CLI smoke test

```bash
vantia init      # creates .vantia tree + state seed if absent
vantia status    # prints task progress, next task, hash-chain status
```

Expected on a fresh checkout: 88 tasks pending, next task `0.1`,
hash chain ok.

---

## 2. Branch model

| Branch | Contents | Purpose |
|---|---|---|
| `main` | application code, engine, tests, docs, workflows, `PLATFORM_STATE.md`, `memory-bank/` | Deployable artefact |
| `vantia-state` | orphan branch: `.vantia/state/state.json`, `.vantia/artifacts/`, `.vantia/run_manifest.json`, `.vantia/README.md` | Authoritative build state + audit trail |

`.vantia/` is **gitignored on `main`** — it must never ship in a deploy.
To stage state files onto the state branch:

```bash
git checkout vantia-state
git add -f .vantia/state/state.json .vantia/artifacts/ .vantia/run_manifest.json .vantia/README.md
git commit -m "vantia: update tracking after <task_id> (run <n>)"
git push origin vantia-state
```

`git add -f` is required because `.vantia/` is ignored.

The two branches share no history by design:

```bash
git merge-base main vantia-state   # must return non-zero (exit 1)
```

If this command returns zero, the branches were accidentally merged and
the isolation guarantee is broken.

---

## 3. CI (`.github/workflows/ci.yml`)

Runs on every push and PR. Steps:

1. Checkout `main`.
2. Set up Python 3.12.
3. `pip install -e . && pip install -r requirements-dev.txt`.
4. `python -m pytest --cov=engine` — **coverage gate: engine >= 90%**.
5. `ruff check engine/ tests/`.
6. Verify YAML parses for all three workflows.

A red CI run blocks merge. Never force-push to `main`.

---

## 4. Keep-alive (three layers)

Render's free tier sleeps a container after ~15 minutes of inactivity.
Vantia defends against that with three independent layers so no single
point of failure can take the engine down.

| Layer | Mechanism | Interval | File |
|---|---|---|---|
| 1 | GitHub Actions cron | every 14 min | `.github/workflows/keep-alive.yml` |
| 2 | In-container self-ping thread (daemon) | every 10 min | `engine/keep_alive.py` |
| 3 | Supabase ping from the same cron | every 14 min | `.github/workflows/keep-alive.yml` |

Layer 2 is a **daemon** thread, so it never blocks process shutdown.
Layer 1 also pings Supabase so the free database tier's 7-day
inactivity pause cannot fire.

During Phase 0 the deployment does not exist yet, so a red keep-alive
cron is expected and deliberately not treated as a failure signal.

---

## 5. Deployment

1. **Backend** → Render free tier, Docker build, `/health` health
   check, `/health` must return 200 in <50 ms.
2. **Frontend** → Vercel Hobby, root `web/`, build via `vercel.json`.
3. **Database** → Supabase free tier; apply `docs/SUPABASE_SETUP.md`.
   Never use Render's free Postgres — it expires after 30 days.
4. **Payments** → Paddle in sandbox mode until launch.

See Phase 6 runbooks for per-platform detail.

---

## 6. Recovery procedures

### 6.1 State file corrupt

The state file is fail-loud by design: a corrupt
`.vantia/state/state.json` **raises** rather than being silently
repaired. Recover from git:

```bash
git checkout vantia-state -- .vantia/state/state.json
```

Never hand-edit the state file. Use `engine.state_manager` for all
mutations so the lock, backup, hash chain and mirror all update
atomically.

### 6.2 Lock file appears stale

A lock file older than the TTL threshold is **refused, not stolen** —
the process exits rather than taking a lock that may belong to a live
writer. Investigate first:

```bash
cat .vantia/state/state.lock
```

If the writer is genuinely gone, remove the file and retry. Stealing a
lock silently is what corrupts state; refusing it is safe.

### 6.3 Hash chain broken

```bash
python scripts/verify_chain.py
```

A broken chain means an artifact was modified after being written.
Treat it as an integrity incident: do not delete the chain to make the
error disappear. Regenerate the run and record the discrepancy in
`PLATFORM_STATE.md` §7.

### 6.4 Task circuit-broken

After 3 consecutive failures a task is marked `blocked` and a GitHub
issue is opened with label `vantia-blocked`. To retry:

1. Read the blocking reason in `PLATFORM_STATE.md` §8.
2. Resolve the underlying cause.
3. Clear `consecutive_failures[task_id]` in `state.json`.
4. Re-run the task in the next session.

### 6.5 Rollback

State changes are additive and every task records its `commit_sha`, so
rollback is a normal git revert on `main` plus reverting the matching
state update on `vantia-state`. Reverted tasks revert to
`in_progress` — never to `complete`.

---

## 7. Credential handling

Never commit credentials. Rules:

- All secrets live in `.env` / `.env.local` (both gitignored).
- `.env.example` lists every variable with a `REPLACE_ME` value.
- LLM keys follow `VANTIA_LLM_<PROVIDER>_KEY`.
- The GitHub credential is used inline for pushes
  (`git push https://oauth2:<token>@github.com/...`) and is never
  written to `.git/config`, `.env`, `state.json`,
  `PLATFORM_STATE.md` or `memory-bank/`.
- Rotate immediately if a credential appears anywhere in a commit or in
  `PLATFORM_STATE.md` / the session log.