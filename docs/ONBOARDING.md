# Vantia — Onboarding

First run:

```bash
bash bootstrap.sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
vantia init
vantia status
```

Or from source: `python3 -m engine.cli status`.

## Status

- **Backend** (FastAPI on Render free): `https://vantia-engine.onrender.com`
- **Frontend** (Next.js on Vercel Hobby): `https://vantia.vercel.app`
- **Status page**: `https://vantia.vercel.app/status`

## Keep-alive (free-tier Render never sleeps)

| Layer | Mechanism | Interval |
|-------|-----------|----------|
| 1 | GitHub Actions cron (`.github/workflows/keep-alive.yml`) | every 14 min |
| 2 | In-container self-ping thread (`engine/keep_alive.py`, started by `engine/api.py`) | every 600 s |
| 3 | UptimeRobot external monitor (optional, manual) | every 5 min |

Render's free tier sleeps a web service after **15 minutes** of inactivity
(~60 h/month total). Both automated layers land inside that window; they
reinforce each other if either is temporarily unavailable.

Set `VANTIA_BACKEND_URL` in repository Settings → Variables so the cron
targets your deployed backend instead of the placeholder URL.
