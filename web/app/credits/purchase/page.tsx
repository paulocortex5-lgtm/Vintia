"use client";

/**
 * Credit purchase page (task 12.5).
 *
 * UI data comes from the engine: `GET /credits/packs` renders the packs and
 * `POST /credits/checkout` opens Paddle Checkout (Paddle is the Merchant of
 * Record — no card data ever reaches Vantia). Failures are shown verbatim
 * from the engine's stable error codes; nothing is faked when Paddle keys
 * are unset.
 *
 * Identity: Phase 8's auth does not exist yet, so the user id is whatever
 * the browser stores locally — honest scaffolding, labelled as such, to be
 * replaced by the verified session when workspaces land.
 */

import { useEffect, useState } from "react";

type Pack = { id: string; tokens: number; price_usd: number | null };

const ENGINE = process.env.NEXT_PUBLIC_ENGINE_URL || "http://localhost:8000";
const USER_KEY = "vantia_user_id";

function formatTokens(tokens: number): string {
  return tokens >= 1000 ? `${Math.round(tokens / 1000)}k` : String(tokens);
}

export default function CreditPurchasePage() {
  const [packs, setPacks] = useState<Pack[]>([]);
  const [environment, setEnvironment] = useState("");
  const [userId, setUserId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setUserId(window.localStorage.getItem(USER_KEY) || "");
    let cancelled = false;
    fetch(`${ENGINE}/credits/packs`)
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        setPacks(Array.isArray(data.packs) ? data.packs : []);
        setEnvironment(data.paddle_environment || "");
        setLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setError(`Engine unreachable at ${ENGINE} — set NEXT_PUBLIC_ENGINE_URL.`);
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function remember(value: string) {
    setUserId(value);
    window.localStorage.setItem(USER_KEY, value);
  }

  async function buy(pack: Pack) {
    setError("");
    if (!userId.trim()) {
      setError("Enter your user ID first (session auth arrives with Phase 8).");
      return;
    }
    setBusy(pack.id);
    try {
      const response = await fetch(`${ENGINE}/credits/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId.trim(), pack_id: pack.id }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data?.detail?.message || `Checkout failed (${response.status}).`);
        return;
      }
      window.location.href = data.checkout_url;
    } catch {
      setError(`Engine unreachable at ${ENGINE} — set NEXT_PUBLIC_ENGINE_URL.`);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Buy credits
        </h1>
        <p className="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400">
          One-time credit packs, paid through{" "}
          <strong>Paddle</strong> (Merchant of Record — we never see your card
          details).{environment ? ` Currently in ${environment} mode.` : ""}
        </p>

        <label className="mt-8 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Your user ID
          <input
            value={userId}
            onChange={(e) => remember(e.target.value)}
            placeholder="e.g. user-123"
            className="mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 font-mono text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100"
          />
          <span className="mt-1 block text-xs font-normal text-zinc-500">
            Placeholder until Phase 8 auth binds this to your signed-in session.
          </span>
        </label>

        {error ? (
          <p
            role="alert"
            className="mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
          >
            {error}
          </p>
        ) : null}

        <ul className="mt-8 flex flex-col gap-4">
          {!loaded && (
            <li className="text-sm text-zinc-500">Loading packs…</li>
          )}
          {loaded && packs.length === 0 && !error && (
            <li className="text-sm text-zinc-500">No packs reported by the engine.</li>
          )}
          {packs.map((pack) => (
            <li
              key={pack.id}
              className="flex items-center justify-between rounded-xl border border-black/10 bg-white px-5 py-4 dark:border-white/15 dark:bg-zinc-950"
            >
              <div>
                <div className="text-lg font-semibold text-black dark:text-zinc-100">
                  {formatTokens(pack.tokens)} credits
                </div>
                <div className="text-sm text-zinc-500">
                  {pack.price_usd === null
                    ? "Price not configured"
                    : `$${pack.price_usd.toFixed(2)} one-time`}
                </div>
              </div>
              <button
                onClick={() => buy(pack)}
                disabled={busy === pack.id}
                className="rounded-full bg-black px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300"
              >
                {busy === pack.id ? "Opening…" : "Buy"}
              </button>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
