# Render Deployment Runbook (task 6.4)

> **Status: NOT DEPLOYED.** This environment has no Render account or
> credentials — the Blueprint below is validated structurally (YAML parse,
> Dockerfile existence, health-path match) by `tests/test_deploy_configs.py`,
> never claimed as live. Follow these steps at launch prep.

## 1. What gets deployed

One web service from the repo-root [`render.yaml`](../render.yaml)
Blueprint (Docker runtime, free plan):

| Setting | Value | Why |
|---|---|---|
| Dockerfile | `./Dockerfile` (digest-pinned `python:3.12-slim`, non-root) | reproducible builds (task 6.3) |
| Health check | `/health` | Render gates rollbacks + routing on it |
| Auto-deploy | `false` | deploys are deliberate until launch confidence exists |
| Self-ping | `VANTIA_SELF_PING=1` | keep-alive layer 2 runs inside the container |

## 2. Deploy steps

1. Push `main` to GitHub (already done — see `docs/RUNBOOK.md` §5).
2. Render → **New → Blueprint** → connect `paulocortex5-lgtm/Vintia`.
3. Render reads `render.yaml`; for every `sync: false` env var, paste the
   value from your password manager (never from git):

   | Env var | Source |
   |---|---|
   | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` | Supabase → Project Settings → API (see `SUPABASE_SETUP.md`) |
   | `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET` | Paddle → Settings (see `PADDLE_SETUP.md`) |
   | `PADDLE_PRICE_PACK_10K/50K/250K` | Paddle price ids (per pack) |
   | `VANTIA_ALLOWED_ORIGINS` | your Vercel domain, e.g. `https://vantia.vercel.app` |

4. Apply Blueprint → wait for the Docker build → `GET /health` must
   return 200.
5. Point the Paddle notification destination at
   `https://<your-service>.onrender.com/paddle/webhook`
   (detailed in `PADDLE_SETUP.md` §1).

## 3. Local verification (no Render account needed)

```bash
docker build -t vantia-engine .     # must succeed with the pinned digest
docker run --rm -p 8000:8000 vantia-engine &
curl -fsS localhost:8000/health     # 200 {"status": "ok", ...}
```

## 4. After go-live checks

- Render logs are single-line JSON (structured logging, task 6.1) —
  grep by `run_id`.
- Free tier sleeps after ~15 min idle: the three-layer keep-alive
  (`docs/KEEP_ALIVE.md`) prevents this; a cold start should still serve
  `/health` within ~30 s.
- Never use Render's free Postgres (expires after 30 days) — Supabase is
  the database (`SUPABASE_SETUP.md`).
