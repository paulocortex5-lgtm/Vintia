# Vercel Deployment Runbook (task 6.5)

> **Status: NOT DEPLOYED.** No Vercel account/credentials exist in this
> environment — [`web/vercel.json`](../web/vercel.json) is validated
> structurally by `tests/test_deploy_configs.py` and the app compiles via
> the `npm run build` gate; nothing here is claimed as live.

## 1. What gets deployed

The Next.js app in [`web/`](../web/) from [`web/vercel.json`](../web/vercel.json):

| Setting | Value | Why |
|---|---|---|
| Framework | `nextjs` | explicit, no auto-detect drift |
| Install | `npm ci` | reproducible from the committed `package-lock.json` |
| Build | `npm run build` | the same gate CI/local runs |
| Root directory | `web/` (set when importing the repo) | app lives in `web/` |

## 2. Deploy steps

1. Vercel → **Add New → Project** → import the GitHub repo.
2. Set **Root Directory** to `web/` (framework preset: Next.js).
3. Environment variables (all `NEXT_PUBLIC_*` — browser-visible by
   definition, so nothing secret goes here):

   | Env var | Value |
   |---|---|
   | `NEXT_PUBLIC_ENGINE_URL` | the Render engine URL (from `RENDER_DEPLOY.md`) |
   | `NEXT_PUBLIC_BASE_URL` | this Vercel deployment's URL |
   | `NEXT_PUBLIC_PADDLE_CLIENT_TOKEN` | Paddle client-side token |
   | `NEXT_PUBLIC_PADDLE_ENVIRONMENT` | `sandbox` until launch |

4. Deploy. Verify: `/` renders, `/credits/purchase` lists packs **once
   `NEXT_PUBLIC_ENGINE_URL` points at a deployed engine**, `/status`
   shows build progress.

## 3. Cross-origin contract

The browser calls the engine directly (CORS, task 12.5): the engine's
`VANTIA_ALLOWED_ORIGINS` (Render env) **must include this Vercel
origin** or requests are refused — that refusal is deliberate; there is
no `*` fallback.

## 4. Honest limits

- Free-tier Hobby is fine for launch but is **non-commercial** — upgrade
  before monetising (tracked in `PLATFORM_STATE.md` §12).
- Preview deployments inherit the same `NEXT_PUBLIC_*` values; they hit
  Paddle **sandbox** prices only while `PADDLE_ENVIRONMENT=sandbox`.
