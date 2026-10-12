# Admin Panel — hidden `/admin` route (NOT DEPLOYED separately).

The administration UI is **not part of the public surface**: no link
anywhere points to `/admin` — you invoke it by typing the path after
your domain (e.g. `https://vantia.vercel.app/admin`). It backs onto the
engine's token-gated `/admin/*` routes (`task: admin panel`, `engine/admin.py`).

> Nothing here is deployed or live until you launch per
> `RENDER_DEPLOY.md` / `VERCEL_DEPLOY.md`: this file documents structure
> only, exactly like those runbooks.

## 1. How to unlock it

1. Generate the API key the panel expects (operator secret, never `NEXT_PUBLIC_*`):
   `openssl rand -hex 32`
2. Put the same value in **two** places:
   - your local gitignored `.env` as `VANTIA_ADMIN_TOKEN=` (Render section);
   - the Render dashboard → Environment as `VANTIA_ADMIN_TOKEN`
     (`render.yaml` marks it `sync: false`, `.env.example` keeps the placeholder).
3. Open `/admin` in the browser, paste the key when prompted.

The panel stores the key only in `localStorage` for the session; the
engine compares it in constant time. While the key is unset on the
engine, **every** admin route answers `503 admin_not_configured`
(fail-closed); a wrong key is `403 admin_forbidden`.

## 2. What the panel manages

| Area | Engine route | Notes |
|---|---|---|
| Overview | `GET /admin/overview` | flags, tier allowances, paid-usage switch, ledger rollup |
| Usage-tier allowances | `PUT /admin/tiers` | monthly tokens per free/pro/business tier, written to state |
| Paid usage tier (paid LLM) | `POST /admin/usage-tier` | writes `llm_policy.allow_paid` in state |
| Per-user credits | `GET /admin/credits?user_id=` | read-only balance/tier/summary |
| Grant / adjust credits | `POST /admin/credits/grant` | idempotent by `ref`; R46: no overdraft |
| Record user tier | `POST /admin/users/tier` | free/pro/business, validated (recorded, never inferred) |

Env vars still win over state (12-factor): where a `VANTIA_*_TIER_TOKENS`,
`VANTIA_FLAG_PAID_LLM` or `VANTIA_ALLOW_PAID_LLM` variable masks a saved
value, the API says so honestly and the panel renders the warning —
re-point the value in Render instead.

## 3. Hiding contract (static-tested in `tests/test_admin_panel.py`)

- Page carries `robots: { index: false, follow: false }`.
- No `href="/admin"` exists in any other file under `web/app`.
- `/admin` is absent from `sitemap.xml` (which lists exactly the public surface).
- `web/app/robots.ts` emits `Disallow: /admin`.
- The `next build` gate compiles the panel (`/admin` appears in the route list).
