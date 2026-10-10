# Keep-Alive Runbook (task 6.7)

> **Status: NOT DEPLOYED** — no Render service exists yet, so the keep-alive
> cron is expected to be red (see "Expected red state" below).

Render's free tier sleeps a container after ~15 minutes of inactivity and
Supabase pauses a free database after 7 days. Vantia defends with **three
independent layers** so no single point of failure can take the platform
down. (Detail lives in `RUNBOOK.md` §4; this file is the focused
operations view.)

| Layer | Mechanism | Interval | File |
|---|---|---|---|
| 1 | GitHub Actions cron pings `/health` | every 14 min | `.github/workflows/keep-alive.yml` |
| 2 | In-container self-ping daemon thread | every 10 min (`VANTIA_SELF_PING_INTERVAL_SEC`) | `engine/keep_alive.py` |
| 3 | The same cron pings Supabase REST | every 14 min | `.github/workflows/keep-alive.yml` |

Notes:

- Layer 2 is a **daemon** thread — it never blocks shutdown; disable it
  with `VANTIA_SELF_PING=0` (tests always do).
- The 14-minute cadence is deliberately just under Render's ~15-minute
  idle window with margin for a slow run.
- Layer 3 exists only for the Supabase 7-day inactivity pause; it pings
  with the anon key and never mutates data.

## Verification

```bash
# layer 2 locally (already covered by tests/test_api.py):
VANTIA_SELF_PING=1 uvicorn engine.api:app &
curl -fsS localhost:8000/health

# layer 1/3: check the workflow's cron trigger and last run in the
# GitHub Actions tab; a red run before the deployment exists is EXPECTED
# (see below).
```

## Expected red state before deployment

During the pre-deploy phase there is no URL to ping, so the keep-alive
cron fails by design and is **not** treated as an incident signal. After
`RENDER_DEPLOY.md` step 2 completes, a red keep-alive run *is* actionable:
check the service sleeps (layer 2 should have prevented it), then inspect
Render logs for JSON lines with the failing `run_id`.

## Failure matrix

| Symptom | Likely layer | Action |
|---|---|---|
| Cron red, engine sleeps anyway | 2 dead | check `VANTIA_SELF_PING` env + startup logs |
| Cron red, engine awake | 1/3 config | workflow secrets/URL wrong |
| Engine awake, Supabase paused | 3 | check `SUPABASE_URL` secret in the workflow |
| All green but slow first request | cold start | normal on free tier; upgrade if p95 hurts |
