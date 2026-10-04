# End-to-end tests (placeholder)

Automated end-to-end coverage for Phase 6 (free-tier deployment, §14).

These tests hit real HTTP boundaries and are intentionally kept out of the
fast unit suite (which runs with no network and no credentials). They cover,
per the v4.0 spec:

* **`test_api_live`** — boot the FastAPI app, `GET /health` returns 200,
  and the self-ping thread keeps the container out of Render's 15-minute
  cold sleep.
* **`test_supabase_write_through`** — with `SUPABASE_URL`/`SUPABASE_ANON_KEY`
  set, state upserts land in Supabase; with them unset, the git mirror
  stays authoritative (graceful degradation, §0.7).
* **`test_keep_alive_cron`** — the GitHub Actions cron hits `/health` on a
  14-minute cadence.
* **`test_paddle_checkout`** — the v6.0 credits/Paddle checkout flow
  (placeholder: requires sandbox Paddle keys).

Until Phase 6 lands, this directory holds no executable tests and the unit
suite does not collect it. Add tests here as the pipeline tasks ship.
