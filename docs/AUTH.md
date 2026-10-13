# Google Sign-In & Admin Bootstrap

Vantia authenticates through **Supabase Auth** — Google OAuth as the
primary path, email/password kept as the honest fallback. No SDK ships
in the browser: the flow is plain redirects plus the GoTrue REST pair
(`NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`, both
publishable by design).

## 1. How the flow works

1. **Start** — `signInWithGoogle()` (`web/lib/engine.ts`) redirects the
   browser to `{SUPABASE_URL}/auth/v1/authorize?provider=google` with
   `redirect_to={origin}/auth/callback`.
2. **Callback** — `web/app/auth/callback/` (noindexed utility route)
   handles both Auth flow shapes, so the dashboard's flow-type setting
   doesn't matter:
   - *implicit*: tokens arrive in the URL fragment; the user id/email
     come from the `id_token` claims (or `GET /auth/v1/user` — never
     client-guessed);
   - *PKCE*: `?code=` is exchanged via
     `POST /auth/v1/token?grant_type=pkce`.
   Either way the session is saved to `localStorage` and the browser is
   sent to `/dashboard`. Provider errors, rejected exchanges and empty
   URLs are each shown verbatim.
3. **Identity** — the verified JWT `sub` is the `user_id` every credit
   and workspace route is keyed by. The engine only ever sees a token.

## 2. First Google sign-in becomes the admin

`supabase/migrations/0007_admin_role.sql` adds `profiles.role`
(`user` | `admin`) and a security-definer trigger on `auth.users`:

- every signup gets a `profiles` row with role `user`;
- the **first google-provider signup** (checked via
  `raw_app_meta_data->'providers'`) is promoted to `admin` — guarded by
  `pg_advisory_xact_lock`, so exactly one account ever claims the slot;
- a backfill promotes the earliest Google account if the migration
  lands after that login;
- the user-writable PostgREST policies (`profiles_insert_own` /
  `profiles_update_own`) require `role = 'user'` — nobody can
  self-promote through the API; only the trigger (or the engine's
  service role) writes roles.

`/admin` (`web/app/admin/AdminGate.tsx`) reads the role with the
signed-in user's own JWT (RLS allows own-row reads only) and renders
the console only for `role = 'admin'`. Not-signed-in, wrong-account,
expired-session, unconfigured-Supabase and missing-migration states are
each displayed honestly. See `docs/ADMIN.md` for the second factor.

## 3. One-time setup (dashboard steps — cannot be scripted)

1. **Google Cloud Console** → APIs & Services → Credentials → OAuth
   client ID (Web application):
   - Authorised redirect URI:
     `https://{SUPABASE_PROJECT_REF}.supabase.co/auth/v1/callback`
   - (Already done for the live project.)
2. **Supabase Dashboard** → Authentication → Providers → Google:
   enable, paste the client ID + secret.
   (Already done for the live project.)
3. **Supabase Dashboard** → Authentication → URL Configuration:
   - Site URL: `https://vantia-rho.vercel.app`
   - Redirect URLs: add `https://vantia-rho.vercel.app/auth/callback`
     and (for local dev) `http://localhost:3000/auth/callback`.
4. **Apply the migration** (in order, after 0001–0006):
   `supabase db push` or paste
   `supabase/migrations/0007_admin_role.sql` into the SQL editor.
5. **Vercel** → project `vantia` → Environment Variables: confirm
   `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   match the Supabase project (publishable values only).

## 4. Verifying

- `/dashboard` → "Continue with Google" → consent → workspace shows
  your Google address and credit balance.
- Sign in with the admin's Google account, open `/admin`: the gate
  passes; the console then asks for the engine key (factor two).
- A second Google account reaches `/admin` but is refused with
  "this account does not carry `role=admin`".
- Static gates: `tests/test_google_auth.py`, `tests/test_admin_panel.py`,
  `tests/test_web_seo.py`.
