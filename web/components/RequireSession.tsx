"use client";

/**
 * Sign-in gate for the application tools — ATS scanner, CV improver,
 * cover letter, credits dashboard and packs. Renders `children` only
 * when a Supabase session exists in `localStorage`; signed-out visitors
 * get an honest "sign in first" card (Google here, email/password on
 * the dashboard). The gate never invents a session and never renders
 * the tool before the session check lands.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { SUPABASE_URL, loadSession, signInWithGoogle } from "../lib/engine";

const button =
  "rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300";
const buttonGhost =
  "rounded-full border border-black/20 px-5 py-2 text-sm font-medium text-black hover:bg-black/5 dark:border-white/30 dark:text-zinc-100 dark:hover:bg-white/10";
const card = "rounded-2xl border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-zinc-950";

export default function RequireSession({
  tool,
  children,
}: {
  tool: string;
  children: React.ReactNode;
}) {
  const [ready, setReady] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => {
    setSignedIn(loadSession() !== null);
    setReady(true);
  }, []);

  function google() {
    if (!signInWithGoogle()) {
      setNote("Sign-in is not configured (NEXT_PUBLIC_SUPABASE_URL missing).");
    }
  }

  if (!ready) {
    return (
      <section className={`${card} mt-8`}>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Checking your session…</p>
      </section>
    );
  }

  if (!signedIn) {
    return (
      <section className={`${card} mt-8`}>
        <h2 className="text-sm font-semibold text-black dark:text-zinc-100">
          {tool} is for signed-in accounts
        </h2>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Sign in with Google, or with email on the dashboard — your free
          monthly allowance starts with the account — and this tool opens
          with your session attached.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          {SUPABASE_URL ? (
            <button type="button" onClick={google} className={button}>
              Continue with Google
            </button>
          ) : null}
          <Link href="/dashboard" className={buttonGhost}>
            Sign in with email
          </Link>
        </div>
        {note ? (
          <p role="status" className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
            {note}
          </p>
        ) : null}
      </section>
    );
  }

  return <>{children}</>;
}
