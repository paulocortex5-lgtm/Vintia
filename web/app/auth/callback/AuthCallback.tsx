"use client";

/**
 * OAuth callback handler — finishes the Supabase sign-in started by
 * `signInWithGoogle()`. Two flow shapes are honoured, so the page works
 * whatever the project's Auth flow-type setting is:
 *
 * 1. Implicit flow: tokens arrive in the URL fragment (`#access_token=…`);
 *    the user id/email come from the `id_token` claims (or `/auth/v1/user`).
 * 2. PKCE flow: `?code=` is exchanged via `POST /auth/v1/token?grant_type=pkce`.
 *
 * Every failure (provider error, missing params, rejected exchange) is
 * shown verbatim — nothing here pretends a sign-in succeeded.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { exchangeAuthCode, sessionFromTokens } from "../../../lib/engine";

export default function AuthCallback() {
  const [note, setNote] = useState("Finishing sign-in…");

  async function finish() {
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const query = new URLSearchParams(window.location.search);

    const error = hash.get("error") || query.get("error");
    if (error) {
      const description = hash.get("error_description") || query.get("error_description");
      setNote(`Sign-in failed: ${error}${description ? ` — ${description}` : ""}.`);
      return;
    }

    const accessToken = hash.get("access_token");
    if (accessToken) {
      const session = await sessionFromTokens({
        access_token: accessToken,
        refresh_token: hash.get("refresh_token") ?? undefined,
        expires_in: Number(hash.get("expires_in")) || undefined,
        id_token: hash.get("id_token") ?? undefined,
      });
      if (!session) {
        setNote("Tokens arrived but no user could be verified — try signing in again.");
        return;
      }
      window.location.replace("/dashboard");
      return;
    }

    const code = query.get("code");
    if (code) {
      const session = await exchangeAuthCode(code);
      if (!session) {
        setNote("The authorization code was rejected — try signing in again.");
        return;
      }
      window.location.replace("/dashboard");
      return;
    }

    setNote("No sign-in result found in the URL — start again from the dashboard.");
  }

  useEffect(() => {
    // `finish` updates note state (setState inside its body); finish is
    // stable (declared in this component), so the dependency array stays empty.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void finish();
  }, []);

  return (
    <section className="rounded-2xl border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-zinc-950">
      <h1 className="text-lg font-semibold tracking-tight text-black dark:text-zinc-50">
        Signing in
      </h1>
      <p role="status" className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        {note}
      </p>
      <Link
        href="/dashboard"
        className="mt-4 inline-block text-sm text-zinc-500 underline hover:text-black dark:hover:text-zinc-100"
      >
        Back to the dashboard
      </Link>
    </section>
  );
}