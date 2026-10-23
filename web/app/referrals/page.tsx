"use client";

/**
 * Referral program (task 15.11 §15.4).
 *
 * Shows the user's referral code, a shareable link with a copy button,
 * and the history of completed referrals. Talks to the engine's
 * `POST /referrals/invite` and `GET /referrals`.
 */

import { useCallback, useEffect, useState } from "react";
import { loadSession } from "../../lib/engine";

const ENGINE_URL = process.env.NEXT_PUBLIC_ENGINE_URL || "http://localhost:8000";

type Invite = { code: string; link: string; share_text: string; bonus_each: number };
type Referral = {
  code: string;
  referee_email: string;
  status: string;
  amount: number;
  created_at: string;
};

export default function ReferralsPage() {
  const [invite, setInvite] = useState<Invite | null>(null);
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [stats, setStats] = useState({ total: 0, completed: 0, credits_earned: 0 });
  const [userId, setUserId] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    const session = loadSession();
    const uid = session?.user?.id || "";
    setUserId(uid);
    if (!uid) {
      setError("Sign in to get your referral link.");
      return;
    }
    try {
      const [inviteRes, histRes] = await Promise.all([
        fetch(`${ENGINE_URL}/referrals/invite?user_id=${encodeURIComponent(uid)}`, {
          method: "POST",
        }),
        fetch(`${ENGINE_URL}/referrals?user_id=${encodeURIComponent(uid)}`),
      ]);
      if (inviteRes.ok) setInvite(await inviteRes.json());
      if (histRes.ok) {
        const data = await histRes.json();
        setReferrals(data.referrals || []);
        setStats({
          total: data.total || 0,
          completed: data.completed || 0,
          credits_earned: data.credits_earned || 0,
        });
      }
      setError("");
    } catch {
      setError(`Could not reach the engine at ${ENGINE_URL}.`);
    }
  }, []);

  useEffect(() => {
    // `load` updates referral state from the engine (setState inside its
    // body, not directly in this effect body).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const copy = async () => {
    if (!invite) return;
    try {
      await navigator.clipboard.writeText(invite.link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 px-6 py-12 font-sans dark:bg-black">
      <main className="mx-auto w-full max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Refer a friend
        </h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          You both get {invite?.bonus_each ?? 5000} credits when a friend signs up with
          your link. No limit on how many friends you refer.
        </p>

        {error ? (
          <p
            role="alert"
            className="mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
          >
            {error}
          </p>
        ) : null}

        {invite ? (
          <div className="mt-6 rounded-xl border border-black/10 bg-white p-5 dark:border-white/10 dark:bg-zinc-950">
            <p className="text-xs text-zinc-500">Your code</p>
            <p className="mt-1 font-mono text-2xl font-semibold tracking-widest text-black dark:text-zinc-50">
              {invite.code}
            </p>
            <div className="mt-4 flex items-center gap-2">
              <input
                readOnly
                value={invite.link}
                className="w-full rounded border border-black/10 bg-zinc-50 px-3 py-2 font-mono text-xs text-zinc-600 dark:border-white/15 dark:bg-zinc-900 dark:text-zinc-300"
              />
              <button
                onClick={copy}
                className="rounded-full bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-white dark:text-black dark:hover:bg-zinc-300"
              >
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
        ) : null}

        <dl className="mt-6 grid grid-cols-3 gap-4 text-center">
          <div className="rounded-xl border border-black/10 bg-white p-4 dark:border-white/10 dark:bg-zinc-950">
            <dt className="text-xs text-zinc-500">Referrals</dt>
            <dd className="text-2xl font-semibold text-black dark:text-zinc-50">{stats.total}</dd>
          </div>
          <div className="rounded-xl border border-black/10 bg-white p-4 dark:border-white/10 dark:bg-zinc-950">
            <dt className="text-xs text-zinc-500">Completed</dt>
            <dd className="text-2xl font-semibold text-emerald-600 dark:text-emerald-400">
              {stats.completed}
            </dd>
          </div>
          <div className="rounded-xl border border-black/10 bg-white p-4 dark:border-white/10 dark:bg-zinc-950">
            <dt className="text-xs text-zinc-500">Credits earned</dt>
            <dd className="text-2xl font-semibold text-black dark:text-zinc-50">
              {stats.credits_earned.toLocaleString()}
            </dd>
          </div>
        </dl>

        <h2 className="mt-8 text-sm font-semibold text-black dark:text-zinc-100">History</h2>
        <ul className="mt-3 flex flex-col gap-2">
          {referrals.map((r, i) => (
            <li
              key={`${r.code}-${i}`}
              className="flex items-center justify-between rounded-lg border border-black/10 bg-white px-4 py-3 text-sm dark:border-white/10 dark:bg-zinc-950"
            >
              <span className="text-zinc-700 dark:text-zinc-300">
                {r.referee_email || "A new member"}
              </span>
              <span className="text-xs text-zinc-500">
                {r.status} · +{r.amount.toLocaleString()} · {r.created_at?.slice(0, 10) || "—"}
              </span>
            </li>
          ))}
          {referrals.length === 0 && !error ? (
            <li className="text-sm text-zinc-400">No referrals yet — share your link to start.</li>
          ) : null}
        </ul>
      </main>
    </div>
  );
}
