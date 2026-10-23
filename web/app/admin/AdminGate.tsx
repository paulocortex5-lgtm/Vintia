"use client";

/**
 * Access gate for `/admin` — the console below renders only for the
 * signed-in account carrying `role = admin` in `profiles` (granted by
 * migration 0007 to the first Google sign-in, never typed in). Identity
 * is the Supabase Auth session; the role is read with the user's own JWT
 * under RLS (own row only). Signed-out, wrong-account, expired-session,
 * unconfigured-Supabase and missing-migration states are each shown
 * verbatim — this gate never fakes access or fakes a denial reason.
 *
 * This is factor one; the engine's fail-closed `VANTIA_ADMIN_TOKEN`
 * stays factor two for every engine-side write (AdminConsole below).
 */

import { useCallback, useEffect, useState } from "react";

import {
  SUPABASE_URL,
  fetchMyRole,
  loadSession,
  signInWithGoogle,
  signOut,
  type Session,
} from "../../lib/engine";

const button =
  "rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300";
const buttonGhost =
  "rounded-full border border-black/20 px-5 py-2 text-sm font-medium text-black hover:bg-black/5 disabled:opacity-50 dark:border-white/30 dark:text-zinc-100 dark:hover:bg-white/10";
const card = "rounded-2xl border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-zinc-950";

type Gate = "loading" | "signin" | "forbidden" | "error" | "allowed";

export default function AdminGate({ children }: { children: React.ReactNode }) {
  const [gate, setGate] = useState<Gate>("loading");
  const [session, setSession] = useState<Session | null>(() => loadSession());
  const [note, setNote] = useState("");

  const evaluate = useCallback(async (current: Session) => {
    const result = await fetchMyRole(current);
    if (!result.ok) {
      if (result.status === 401 || result.status === 403) {
        signOut();
        setSession(null);
        setNote(result.message);
        setGate("signin");
        return;
      }
      setNote(result.message);
      setGate("error");
      return;
    }
    if (result.role === "admin") {
      setGate("allowed");
      return;
    }
    setGate("forbidden");
  }, []);

  useEffect(() => {
    // Session is seeded lazily on first render; this effect evaluates the
    // admin role (async, which calls setState) and sets the gate.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!session) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setGate("signin");
      return;
    }
    // `evaluate` updates gate state (setState inside its body).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void evaluate(session);
  }, [session, evaluate]);

  function google() {
    if (!signInWithGoogle()) {
      setNote("Sign-in is not configured (NEXT_PUBLIC_SUPABASE_URL missing).");
      setGate("error");
    }
  }

  function logout() {
    signOut();
    setSession(null);
    setGate("signin");
    setNote("");
  }

  if (gate === "loading") {
    return (
      <section className={`${card} mt-8`}>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Checking admin access…</p>
      </section>
    );
  }

  if (gate === "signin") {
    return (
      <section className={`${card} mt-8`}>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          This panel is limited to the Vantia admin account. Sign in with the
          Google account that owns the site — the first Google sign-in was
          granted <code className="font-mono">role=admin</code> automatically
          (migration 0007). Everyone else is refused below, honestly.
        </p>
        {SUPABASE_URL ? (
          <button type="button" onClick={google} className={`${button} mt-4`}>
            Continue with Google
          </button>
        ) : (
          <p className="mt-4 text-sm text-zinc-500">
            Sign-in is not configured (NEXT_PUBLIC_SUPABASE_URL missing).
          </p>
        )}
        {note ? (
          <p role="status" className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
            {note}
          </p>
        ) : null}
      </section>
    );
  }

  if (gate === "forbidden") {
    return (
      <section className={`${card} mt-8`}>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Signed in as{" "}
          <span className="font-medium text-black dark:text-zinc-100">
            {session?.user.email ?? session?.user.id}
          </span>{" "}
          — this account does not carry <code className="font-mono">role=admin</code>,
          so the admin panel stays closed. (Only the first Google sign-in was
          promoted.)
        </p>
        <button type="button" onClick={logout} className={`${buttonGhost} mt-4`}>
          Sign out
        </button>
      </section>
    );
  }

  if (gate === "error") {
    return (
      <section className={`${card} mt-8`}>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">{note}</p>
        <div className="mt-4 flex gap-3">
          <button type="button" onClick={() => session && void evaluate(session)} className={buttonGhost}>
            Retry
          </button>
          <button type="button" onClick={logout} className={buttonGhost}>
            Sign out
          </button>
        </div>
      </section>
    );
  }

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-zinc-500">
          Admin session:{" "}
          <span className="font-medium text-black dark:text-zinc-100">
            {session?.user.email ?? session?.user.id}
          </span>
        </p>
        <button type="button" onClick={logout} className={buttonGhost}>
          Sign out
        </button>
      </div>
      {children}
    </div>
  );
}