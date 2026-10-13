"use client";

/**
 * Credit purchase page (task 12.5) — gated behind the session since the
 * tools became sign-in-only: packs are bought against the verified session
 * user id (JWT `sub`), never a typed placeholder.
 *
 * UI data comes from the engine: `GET /credits/packs` renders the packs and
 * `POST /credits/checkout` opens Paddle Checkout (Paddle is the Merchant of
 * Record — no card data ever reaches Vantia). Failures are shown verbatim
 * from the engine's stable error codes; nothing is faked when Paddle keys
 * are unset.
 */

import { useEffect, useState } from "react";

import RequireSession from "../../../components/RequireSession";
import { ENGINE, loadSession, type Session } from "../../../lib/engine";

type Pack = { id: string; tokens: number; price_usd: number | null };

function formatTokens(tokens: number): string {
  return tokens >= 1000 ? `${Math.round(tokens / 1000)}k` : String(tokens);
}

export default function CreditPurchasePage() {
  return (
    <RequireSession tool="Credit packs">
      <PurchaseInner />
    </RequireSession>
  );
}

function PurchaseInner() {
  const [session, setSession] = useState<Session | null>(null);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [environment, setEnvironment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    setSession(loadSession());
    let cancelled = false;
    fetch(`${ENGINE}/credits/packs`)
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        setPacks(Array.isArray(data.packs) ? data.packs : []);
        setEnvironment(data.paddle_environment || "");
      })
      .catch(() => {
        if (cancelled) return;
        setError(`Engine unreachable at ${ENGINE}.`);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function buy(pack: Pack) {
    setError("");
    const userId = session?.user.id;
    if (!userId) {
      setError("Session expired — sign in again to buy packs against your account.");
      return;
    }
    setBusy(pack.id);
    try {
      const response = await fetch(`${ENGINE}/credits/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, pack_id: pack.id }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data?.detail?.message || `Checkout failed (${response.status}).`);
        return;
      }
      window.location.href = data.checkout_url;
    } catch {
      setError(`Engine unreachable at ${ENGINE}.`);
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
          details).{environment ? ` Currently in ${environment} mode.` : ""} Bought
          against{" "}
          <span className="font-mono text-xs">
            {session?.user.email ?? session?.user.id ?? "your account"}
          </span>
          .
        </p>

        {error ? (
          <p
            role="alert"
            className="mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
          >
            {error}
          </p>
        ) : null}

        <ul className="mt-8 flex flex-col gap-4">
          {packs.length === 0 && !error && (
            <li className="text-sm text-zinc-500">Loading packs…</li>
          )}
          {packs.length === 0 && error && (
            <li className="text-sm text-zinc-500">No packs could be loaded.</li>
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
