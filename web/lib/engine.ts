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

/** Stable error message from an engine `as_dict()` body. */
export function engineError(body: unknown, status: number): string {
  const detail = (body as { detail?: { message?: string; error?: string } })?.detail;
  if (detail?.message) return `${detail.message} (${detail.error || status})`;
  return `Engine request failed (${status}).`;
}