"""Static Google-auth surface tests (sign-in, callback, admin bootstrap).

The flow itself can't run offline — Supabase and Google live out there —
so these verify what text files can prove: the OAuth redirect targets
`/auth/v1/authorize?provider=google`, the callback handles both flow
shapes and is noindexed, the dashboard offers Google sign-in, the
migration promotes exactly one first-Google admin and refuses
self-promotion through PostgREST, and no browser bundle ever carries an
operator secret.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
MIGRATION = ROOT / "supabase" / "migrations" / "0007_admin_role.sql"

ENGINE_LIB = (WEB / "lib" / "engine.ts").read_text("utf-8")
DASHBOARD = (WEB / "app" / "dashboard" / "Dashboard.tsx").read_text("utf-8")
CALLBACK_PAGE = (WEB / "app" / "auth" / "callback" / "page.tsx").read_text("utf-8")
CALLBACK = (WEB / "app" / "auth" / "callback" / "AuthCallback.tsx").read_text("utf-8")
HOME = (WEB / "app" / "page.tsx").read_text("utf-8")


# ── the OAuth redirect ──────────────────────────────────────────────────


def test_engine_lib_starts_the_google_oauth_flow():
    assert "/auth/v1/authorize?provider=google" in ENGINE_LIB
    # the round trip lands on the callback route, never a third party
    assert '"/auth/callback"' in ENGINE_LIB


def test_callback_handles_both_flow_shapes():
    # implicit flow: tokens in the URL fragment
    assert "access_token" in CALLBACK and "sessionFromTokens" in CALLBACK
    # pkce flow: the ?code= exchange
    assert "grant_type=pkce" in ENGINE_LIB and "exchangeAuthCode" in CALLBACK
    # provider errors are surfaced verbatim, never swallowed
    assert "error_description" in CALLBACK


def test_callback_page_is_noindex_utility_route():
    assert "export const metadata" in CALLBACK_PAGE
    assert "robots: { index: false, follow: false }" in CALLBACK_PAGE
    sitemap = (WEB / "app" / "sitemap.xml" / "route.ts").read_text("utf-8")
    assert "auth/callback" not in sitemap


def test_session_identity_never_comes_from_client_guesswork():
    # sub/email come from the id_token claims or GET /auth/v1/user
    assert "decodeJwtPayload" in ENGINE_LIB
    assert "/auth/v1/user" in ENGINE_LIB
    assert "fetchMyRole" in ENGINE_LIB  # role read server-side via RLS


# ── the sign-in surfaces ────────────────────────────────────────────────


def test_dashboard_offers_google_next_to_email_password():
    assert "Continue with Google" in DASHBOARD
    assert "signInWithGoogle" in DASHBOARD
    # email/password stays the honest fallback
    assert "signIn" in DASHBOARD and "signUp" in DASHBOARD


def test_homepage_points_at_the_dashboard_not_the_waitlist():
    assert 'href="/dashboard"' in HOME
    assert 'href="/waitlist"' not in HOME


# ── the admin bootstrap migration ───────────────────────────────────────


def test_migration_ships_and_is_transactional():
    assert MIGRATION.exists(), "0007_admin_role.sql is missing"
    sql = MIGRATION.read_text("utf-8")
    assert "begin;" in sql
    assert sql.rstrip().endswith("commit;")


def test_migration_promotes_only_the_first_google_login():
    sql = MIGRATION.read_text("utf-8")
    assert "add column if not exists role" in sql
    assert "check (role in ('user', 'admin'))" in sql
    # google-provider eligibility — email/password can never claim the slot
    assert "'providers' ? 'google'" in sql
    # exactly one first admin, even under concurrent signups
    assert "pg_advisory_xact_lock" in sql
    assert "not exists (select 1 from public.profiles where role = 'admin')" in sql


def test_migration_refuses_self_promotion_through_postgrest():
    sql = MIGRATION.read_text("utf-8")
    # the user-writable insert/update policies must exclude role=admin
    assert 'create policy "profiles_insert_own"' in sql
    assert 'create policy "profiles_update_own"' in sql
    assert "and role = 'user')" in sql
    # writes go through a security-definer trigger, never the client
    assert "security definer" in sql
    # anon has no business here at all
    assert "revoke all on public.profiles from anon" in sql


def test_no_operator_secret_reaches_the_browser_bundle():
    """The env-var *name* may appear as setup help; values and access never do.

    `engine.ts` reads the publishable NEXT_PUBLIC_* pair by design, so the
    `process.env` ban applies only to the auth/admin components.
    """
    for path in (
        WEB / "lib" / "engine.ts",
        WEB / "app" / "auth" / "callback" / "AuthCallback.tsx",
        WEB / "app" / "admin" / "AdminGate.tsx",
    ):
        text = path.read_text("utf-8")
        assert "NEXT_PUBLIC_ADMIN_TOKEN" not in text, path
        assert "SERVICE_ROLE" not in text, path
        # no credential-shaped literals (publishable keys, secret keys, tokens)
        for marker in ("sb_secret_", "sb_publishable_", "rnd_", "ghp_"):
            assert marker not in text, path
    for path in (
        WEB / "app" / "auth" / "callback" / "AuthCallback.tsx",
        WEB / "app" / "admin" / "AdminGate.tsx",
    ):
        assert "process.env" not in path.read_text("utf-8"), path
