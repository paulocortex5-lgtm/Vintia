import { NextResponse } from "next/server";

/**
 * Google sign-in entry point (server-side preflight).
 *
 * The browser never navigates to Supabase directly: this route asks
 * GoTrue for the Google authorize redirect first (server fetches are not
 * CORS-limited, and `redirect: "manual"` exposes the Location header).
 *
 * - Provider enabled + redirect allowlisted → the browser is forwarded
 *   to the Google consent URL (the 302 from `/auth/v1/authorize`).
 * - Anything else (provider disabled, redirect URL not allowed, ...):
 *   the browser is sent to `/auth/callback` with the *verbatim* Supabase
 *   error, so the failure is shown in the product — never as a raw JSON
 *   page on `*.supabase.co` (whose favicon404s, by the way).
 *
 * Fail-closed and honest: a missing server env pair or an unreachable
 * Supabase each land on the callback page with the exact reason.
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";

function refuse(request: Request, code: string, description: string): NextResponse {
  const target = new URL("/auth/callback", request.url);
  target.searchParams.set("error", code);
  target.searchParams.set("error_description", description);
  return NextResponse.redirect(target, 302);
}

export async function GET(request: Request): Promise<NextResponse> {
  if (!SUPABASE_URL) {
    return refuse(
      request,
      "not_configured",
      "Sign-in is not configured on the server (NEXT_PUBLIC_SUPABASE_URL missing)."
    );
  }

  const redirect = `${new URL(request.url).origin}/auth/callback`;
  const authorize =
    `${SUPABASE_URL}/auth/v1/authorize?provider=google` +
    `&redirect_to=${encodeURIComponent(redirect)}`;

  let response: Response;
  // one bounded retry: a cold serverless start can drop the first DNS
  // lookup — that must not be shown to the user as "unreachable"
  const attempt = () =>
    fetch(authorize, { redirect: "manual", cache: "no-store", signal: AbortSignal.timeout(15_000) });
  try {
    response = await attempt();
  } catch (first) {
    try {
      response = await attempt();
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      return refuse(
        request,
        "supabase_unreachable",
        `Supabase unreachable at ${SUPABASE_URL} (${reason}, after a retry — first error: ${
          first instanceof Error ? first.message : String(first)
        }).`
      );
    }
  }

  const location = response.headers.get("location");
  if (response.status >= 300 && response.status < 400 && location) {
    return NextResponse.redirect(location, 302);
  }

  const body = await response.text();
  let message = body;
  try {
    const data = JSON.parse(body) as { msg?: string; error_description?: string; message?: string };
    message = data.msg || data.error_description || data.message || body;
  } catch {
    /* keep the raw body — nothing is paraphrased */
  }
  return refuse(
    request,
    "google_sign_in_refused",
    `${message} — to fix, enable the Google provider (Supabase dashboard → Authentication → ` +
      `Providers → Google) and add ${redirect} to Authentication → URL Configuration → ` +
      `Redirect URLs. See docs/AUTH.md §3.`
  );
}
