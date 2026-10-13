"use client";

/**
 * Workspace dashboard (task 13.1) — engine status, sign-in and the credit
 * balance in one place. Identity is the Supabase Auth session — Google
 * OAuth (via `/auth/v1/authorize` + the /auth/callback page) with
 * email/password as the honest fallback; the verified `sub` becomes the
 * `user_id` every credit route is keyed by. Nothing here invents state:
 * an unreachable engine or a missing Supabase pair is shown, not hidden.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  ENGINE,
  SUPABASE_URL,
  engineError,
  loadSession,
  signIn,
  signInWithGoogle,
  signOut,
  signUp,
  type Session,
} from "../../lib/engine";

type EngineStatus = {
  initialised: boolean;
  total: number;
  complete: number;
  pending: number;
  readiness_pct: number;
  run_count: number;
  last_completed_task: string | null;
};
type Balance = {
  balance: number;
  tier: string;
  monthly_allowance: number;
  entry_count: number;
};

const input =
  "mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100";
const label = "text-sm font-medium text-zinc-700 dark:text-zinc-300";
const button =
  "rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300";
const card = "rounded-2xl border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-zinc-950";

const TOOLS = [
  { href: "/ats", title: "ATS scanner", note: "Upload or paste — twelve-point score" },
  { href: "/improve", title: "CV improver", note: "Fact-preserving, ranked edits" },
  { href: "/cover-letter", title: "Cover letter", note: "Facts-only, from your resume + posting" },
  { href: "/credits/dashboard", title: "Credits", note: "Balance, allowance, packs, invoices" },
];

export default function Dashboard() {
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [balance, setBalance] = useState<Balance | null>(null);
  const [engineNote, setEngineNote] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"signin" | "signup">("signin");

  useEffect(() => {
    setSession(loadSession());
    fetch(`${ENGINE}/status`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data?.initialised && setStatus(data as EngineStatus))
      .catch(() => setEngineNote(`Engine unreachable at ${ENGINE}.`));
  }, []);

  const loadBalance = useCallback((current: Session | null) => {
    if (!current) return;
    fetch(`${ENGINE}/credits/balance?user_id=${encodeURIComponent(current.user.id)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && setBalance(data as Balance))
      .catch(() => setBalance(null));
  }, []);

  useEffect(() => {
    loadBalance(session);
  }, [session, loadBalance]);

  async function authenticate(e: React.FormEvent) {
    e.preventDefault();
    if (!SUPABASE_URL) {
      setAuthMessage("Sign-in is not configured yet (NEXT_PUBLIC_SUPABASE_URL missing).");
      return;
    }
    setBusy(true);
    setAuthMessage("");
    try {
      if (mode === "signup") {
        const response = await signUp(email, password);
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          setAuthMessage(engineError(body, response.status));
          return;
        }
        setAuthMessage("Account created. If email confirmation is on, click the link we sent, then sign in.");
        setMode("signin");
        return;
      }
      const signed = await signIn(email, password);
      if (!signed) {
        setAuthMessage("Sign-in failed — wrong credentials, or the confirmation email is still unclicked.");
        return;
      }
      setSession(signed);
      setAuthMessage("");
    } finally {
      setBusy(false);
    }
  }

  function google() {
    if (!signInWithGoogle()) {
      setAuthMessage("Sign-in is not configured (NEXT_PUBLIC_SUPABASE_URL missing).");
    }
  }

  function logout() {
    signOut();
    setSession(null);
    setBalance(null);
  }

  return (
    <div className="mt-8 flex flex-col gap-6">
      {/* Engine status card */}
      <section className={card}>
        <h2 className="text-sm font-medium text-zinc-500">Engine status</h2>
        {status ? (
          <div className="mt-2 flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <span className="text-3xl font-semibold text-black dark:text-zinc-50">
              {status.readiness_pct}%
            </span>
            <span className="text-sm text-zinc-500">
              {status.complete}/{status.total} tasks · run {status.run_count} · last:{" "}
              {status.last_completed_task ?? "—"}
            </span>
          </div>
        ) : (
          <p className="mt-2 text-sm text-zinc-500">{engineNote || "Loading status…"}</p>
        )}
      </section>

      {/* Session / auth card */}
      <section className={card}>
        <h2 className="text-sm font-medium text-zinc-500">Account</h2>
        {session ? (
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-black dark:text-zinc-100">
                {session.user.email ?? "signed in"}
              </p>
              {balance ? (
                <p className="mt-1 text-sm text-zinc-500">
                  {balance.balance.toLocaleString()} credits · {balance.tier} tier ·{" "}
                  {balance.monthly_allowance.toLocaleString()}/month allowance
                </p>
              ) : (
                <p className="mt-1 text-sm text-zinc-500">Loading balance…</p>
              )}
            </div>
            <button type="button" onClick={logout} className="rounded-full border border-black/10 px-4 py-1.5 text-sm text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100">
              Sign out
            </button>
          </div>
        ) : (
          <div className="mt-3 flex flex-col gap-3">
            <button
              type="button"
              onClick={google}
              disabled={!SUPABASE_URL}
              className={button}
            >
              Continue with Google
            </button>
            <p className="text-xs text-zinc-500">or use email —</p>
            <form onSubmit={authenticate} className="flex flex-col gap-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className={label}>
                  Email
                  <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={input} placeholder="you@example.com" />
                </label>
                <label className={label}>
                  Password
                  <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} className={input} />
                </label>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button type="submit" disabled={busy} className={button}>
                  {busy ? "Working…" : mode === "signin" ? "Sign in" : "Create account"}
                </button>
                <button
                  type="button"
                  onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
                  className="text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
                >
                  {mode === "signin" ? "New here? Create an account" : "Have an account? Sign in"}
                </button>
              </div>
            </form>
            {authMessage ? (
              <p role="status" className="text-sm text-zinc-600 dark:text-zinc-400">{authMessage}</p>
            ) : null}
          </div>
        )}
      </section>

      {/* Tool links */}
      <section className="grid gap-3 sm:grid-cols-2">
        {TOOLS.map((tool) => (
          <Link
            key={tool.href}
            href={tool.href}
            className={`${card} block transition hover:border-black/30 dark:hover:border-white/30`}
          >
            <h2 className="text-sm font-semibold text-black dark:text-zinc-100">{tool.title}</h2>
            <p className="mt-1 text-xs text-zinc-500">{tool.note}</p>
          </Link>
        ))}
      </section>

      <p className="text-xs text-zinc-500">
        Sign-in runs through Supabase Auth — Google OAuth or email/password —
        the engine only ever sees a verified token, and the service-role key
        never leaves the server. Without a session the tools still work; you
        just are not saving anything yet.
      </p>
    </div>
  );
}

