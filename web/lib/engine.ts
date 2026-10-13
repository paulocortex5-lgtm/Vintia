/** Engine base URL the browser calls (same-origin `/api` in deployment). */
export const ENGINE = process.env.NEXT_PUBLIC_ENGINE_URL || "http://localhost:8000";

/** Supabase Auth REST pair — publishable values only, never service-role. */
export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

export type Session = {
  access_token: string;
  refresh_token: string;
  expires_at?: number;
  user: { id: string; email?: string };
};

const SESSION_KEY = "vantia_session";

export function loadSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as Session;
    return session?.access_token && session?.user?.id ? session : null;
  } catch {
    return null;
  }
}

export function saveSession(session: Session | null) {
  if (typeof window === "undefined") return;
  if (session) window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  else window.localStorage.removeItem(SESSION_KEY);
}

/** Sign up through Supabase Auth REST — no SDK, no secret in the browser. */
export async function signUp(email: string, password: string): Promise<Response> {
  return fetch(`${SUPABASE_URL}/auth/v1/signup`, {
    method: "POST",
    headers: { apikey: SUPABASE_ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

/** Password grant → session (or null; the caller shows the honest reason). */
export async function signIn(email: string, password: string): Promise<Session | null> {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: SUPABASE_ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) return null;
  const data = (await response.json()) as { access_token: string; refresh_token: string; user?: { id: string; email?: string } };
  if (!data.access_token || !data.user?.id) return null;
  const session: Session = {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    user: data.user,
  };
  saveSession(session);
  return session;
}

export function signOut() {
  saveSession(null);
}

/**
 * Start the Supabase OAuth flow (Google) — a full-page redirect through
 * `/auth/v1/authorize`; the session lands back on `/auth/callback`.
 * Returns false when the Supabase pair isn't configured (the caller
 * shows the honest reason — nothing here fakes a redirect).
 */
export function signInWithGoogle(redirectPath = "/auth/callback"): boolean {
  if (!SUPABASE_URL) return false;
  const redirect =
    typeof window === "undefined"
      ? redirectPath
      : `${window.location.origin}${redirectPath}`;
  window.location.assign(
    `${SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to=${encodeURIComponent(redirect)}`
  );
  return true;
}

/** Decode a JWT payload without verifying (claims come from the callback
 * URL we just received from Supabase; the engine still verifies tokens). */
function decodeJwtPayload(token: string): Record<string, string> | null {
  try {
    const payload = token.split(".")[1];
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64)) as Record<string, string>;
  } catch {
    return null;
  }
}

/**
 * Build a Session from raw OAuth tokens (implicit-flow hash params or a
 * PKCE exchange response). The user id comes from the `id_token` claims,
 * falling back to `GET /auth/v1/user` — never invented.
 */
export async function sessionFromTokens(tokens: {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  id_token?: string;
}): Promise<Session | null> {
  if (!tokens.access_token) return null;
  let id = "";
  let email: string | undefined;
  if (tokens.id_token) {
    const claims = decodeJwtPayload(tokens.id_token);
    id = claims?.sub ?? "";
    email = claims?.email;
  }
  if (!id) {
    const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
      headers: { apikey: SUPABASE_ANON_KEY, Authorization: `Bearer ${tokens.access_token}` },
    });
    if (!response.ok) return null;
    const user = (await response.json()) as { id?: string; email?: string };
    id = user.id ?? "";
    email = user.email;
  }
  if (!id) return null;
  const session: Session = {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token ?? "",
    expires_at: tokens.expires_in
      ? Math.floor(Date.now() / 1000) + tokens.expires_in
      : undefined,
    user: { id, email },
  };
  saveSession(session);
  return session;
}

/** Exchange a PKCE authorization code (`?code=` on the callback URL) for a session. */
export async function exchangeAuthCode(code: string): Promise<Session | null> {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=pkce`, {
    method: "POST",
    headers: { apikey: SUPABASE_ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ auth_code: code }),
  });
  if (!response.ok) return null;
  const data = (await response.json()) as {
    access_token: string;
    refresh_token: string;
    expires_in?: number;
    user?: { id: string; email?: string };
  };
  if (!data.access_token) return null;
  if (data.user?.id) {
    // The exchange response already carries the user — save directly.
    const session: Session = {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      expires_at: data.expires_in
        ? Math.floor(Date.now() / 1000) + data.expires_in
        : undefined,
      user: { id: data.user.id, email: data.user.email },
    };
    saveSession(session);
    return session;
  }
  return sessionFromTokens({
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    expires_in: data.expires_in,
  });
}

export type RoleCheck =
  | { ok: true; role: string | null }
  | { ok: false; status: number; message: string };

/**
 * Read the signed-in user's `profiles.role` through PostgREST with the
 * user's own JWT (RLS allows own-row reads only). The admin gate keys on
 * this — role is granted by migration 0007, never typed in.
 */
export async function fetchMyRole(session: Session): Promise<RoleCheck> {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    return {
      ok: false,
      status: 0,
      message:
        "Sign-in is not configured (NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY missing).",
    };
  }
  try {
    const response = await fetch(
      `${SUPABASE_URL}/rest/v1/profiles?user_id=eq.${encodeURIComponent(
        session.user.id
      )}&select=role`,
      {
        headers: {
          apikey: SUPABASE_ANON_KEY,
          Authorization: `Bearer ${session.access_token}`,
        },
      }
    );
    if (response.status === 401 || response.status === 403) {
      return { ok: false, status: response.status, message: "Session rejected — sign in again." };
    }
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        message:
          `profiles lookup failed (${response.status}) — ` +
          "has supabase/migrations/0007_admin_role.sql been applied?",
      };
    }
    const rows = (await response.json()) as { role: string | null }[];
    return { ok: true, role: rows[0]?.role ?? null };
  } catch {
    return { ok: false, status: 0, message: `Supabase unreachable at ${SUPABASE_URL}.` };
  }
}

/** Stable error message from an engine `as_dict()` body. */
export function engineError(body: unknown, status: number): string {
  const detail = (body as { detail?: { message?: string; error?: string } })?.detail;
  if (detail?.message) return `${detail.message} (${detail.error || status})`;
  return `Engine request failed (${status}).`;
}