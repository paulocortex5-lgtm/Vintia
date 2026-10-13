"use client";

/**
 * Credits dashboard (task 13.5) — balance, tier, allowance, recent ledger
 * entries, packs and the monthly statement, all read live from the engine.
 * The page renders only behind the session gate — balance, allowance, packs
 * and invoices are account data, so signed-out visitors get the honest
 * "sign in first" card instead of the dashboard. Nothing is estimated or
 * faked client-side.
 */

import { useEffect, useState } from "react";

import RequireSession from "../../../components/RequireSession";
import {
  ENGINE,
  engineError,
  loadSession,
  type Session,
} from "../../../lib/engine";

type Balance = {
  user_id: string;
  balance: number;
  tier: string;
  monthly_allowance: number;
  allowance: { granted: boolean; month: string; amount: number };
  operations: Record<string, number>;
  packs: { id: string; tokens: number; price_usd: number | null }[];
  recent_entries: { id?: string; amount?: number; reason?: string; created_at?: string }[];
  entry_count: number;
};
type Pack = { id: string; tokens: number; price_usd: number | null };
type Invoice = { period: string; unit?: string; invoice_id?: string } | null;

const input =
  "mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100";
const button =
  "rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300";
const card = "rounded-2xl border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-zinc-950";

function CreditsDashboardInner() {
  const [session, setSession] = useState<Session | null>(null);
  const [userId, setUserId] = useState("");
  const [balance, setBalance] = useState<Balance | null>(null);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [invoice, setInvoice] = useState<Invoice>(null);
  const [invoiceNote, setInvoiceNote] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const existing = loadSession();
    setSession(existing);
    setUserId(existing?.user.id ?? "");
    fetch(`${ENGINE}/credits/packs`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data?.packs && setPacks(data.packs as Pack[]))
      .catch(() => setPacks([]));
  }, []);

  useEffect(() => {
    if (!userId) return;
    fetch(`${ENGINE}/credits/balance?user_id=${encodeURIComponent(userId)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && setBalance(data as Balance))
      .catch(() => setBalance(null));
    fetch(`${ENGINE}/credits/invoices?user_id=${encodeURIComponent(userId)}`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data) => setInvoice(data as Invoice))
      .catch((status: number) =>
        setInvoiceNote(
          typeof status === "number"
            ? "Statement unavailable — the invoice feature flag is off."
            : "Statement unavailable."
        )
      );
  }, [userId]);

  async function checkout(packId: string) {
    if (!userId) {
      setNote("Sign in on the dashboard first — checkout is keyed to your user id.");
      return;
    }
    setBusy(true);
    setNote("");
    try {
      const response = await fetch(`${ENGINE}/credits/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, pack_id: packId }),
      });
      const data = await response.json();
      if (!response.ok) {
        setNote(engineError(data, response.status));
        return;
      }
      if (data.checkout_url) window.location.href = data.checkout_url as string;
      else setNote("Checkout returned no URL — check the Paddle configuration.");
    } catch {
      setNote(`Engine unreachable at ${ENGINE}.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-3xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Credits dashboard
        </h1>
        <p className="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400">
          Every price and balance below is read live from the engine — nothing is
          estimated in the browser.
        </p>

        {!session ? (
          <section className={`${card} mt-6`}>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              You are browsing as a guest. Sign in on the{" "}
              <a href="/dashboard" className="underline hover:text-black dark:hover:text-zinc-100">
                dashboard
              </a>{" "}
              to see your balance, statement and buy packs against your account.
            </p>
          </section>
        ) : (
          <section className={`${card} mt-6`}>
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <div>
                <span className="text-4xl font-semibold text-black dark:text-zinc-50">
                  {balance ? balance.balance.toLocaleString() : "—"}
                </span>
                <span className="ml-2 text-sm text-zinc-500">credits</span>
              </div>
              {balance ? (
                <span className="rounded-full bg-black/5 px-3 py-1 text-xs font-medium capitalize dark:bg-white/10">
                  {balance.tier} tier · {balance.monthly_allowance.toLocaleString()}/mo
                </span>
              ) : null}
            </div>
            {balance ? (
              <p className="mt-2 text-xs text-zinc-500">
                {balance.allowance.granted
                  ? `Monthly allowance granted for ${balance.allowance.month}.`
                  : `Allowance for ${balance.allowance.month} not yet claimed — it is projected, not granted, until a metered run.`}{" "}
                {balance.entry_count} ledger entries.
              </p>
            ) : (
              <p className="mt-2 text-xs text-zinc-500">Loading balance…</p>
            )}

            {balance && Object.keys(balance.operations).length ? (
              <div className="mt-4">
                <h2 className="text-sm font-medium text-zinc-500">Operation prices</h2>
                <ul className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
                  {Object.entries(balance.operations).map(([op, cost]) => (
                    <li key={op} className="flex justify-between rounded-lg bg-black/[.03] px-3 py-1.5 dark:bg-white/[.05]">
                      <span className="capitalize text-zinc-700 dark:text-zinc-300">{op.replace(/_/g, " ")}</span>
                      <span className="font-mono text-zinc-500">{cost.toLocaleString()}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {balance?.recent_entries?.length ? (
              <div className="mt-4">
                <h2 className="text-sm font-medium text-zinc-500">Recent ledger entries</h2>
                <ul className="mt-2 flex flex-col gap-1 text-xs">
                  {balance.recent_entries.slice(-8).reverse().map((entry, index) => (
                    <li key={index} className="flex justify-between text-zinc-600 dark:text-zinc-400">
                      <span>{entry.reason ?? "movement"}</span>
                      <span className="font-mono">
                        {(entry.amount ?? 0) > 0 ? "+" : ""}
                        {(entry.amount ?? 0).toLocaleString()}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        )}

        {invoice ? (
          <section className={`${card} mt-6`}>
            <h2 className="text-sm font-medium text-zinc-500">Statement · {invoice.period}</h2>
            <pre className="mt-2 whitespace-pre-wrap font-mono text-xs text-zinc-600 dark:text-zinc-400">
              {JSON.stringify(invoice, null, 2)}
            </pre>
          </section>
        ) : invoiceNote && session ? (
          <p className="mt-4 text-xs text-zinc-500">{invoiceNote}</p>
        ) : null}

        <section className="mt-6">
          <h2 className="text-sm font-medium text-zinc-500">Credit packs</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {(packs.length ? packs : balance?.packs ?? []).map((pack) => (
              <div key={pack.id} className={`${card} flex flex-col gap-2`}>
                <span className="text-lg font-semibold text-black dark:text-zinc-100">
                  {pack.tokens.toLocaleString()}
                </span>
                <span className="text-xs text-zinc-500">
                  {pack.price_usd === null ? "price not configured" : `$${pack.price_usd.toFixed(2)} one-time`}
                </span>
                <button
                  type="button"
                  disabled={busy || pack.price_usd === null}
                  onClick={() => checkout(pack.id)}
                  className={`${button} mt-2`}
                >
                  Buy
                </button>
              </div>
            ))}
          </div>
        </section>

        {note ? (
          <p role="status" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {note}
          </p>
        ) : null}

        <p className="mt-8 text-xs text-zinc-500">
          Payments run through Paddle (Merchant of Record) — Vantia never touches
          your card details. In demo/sandbox mode checkout URLs are only issued
          when the Paddle price ids are configured.
        </p>
      </main>
    </div>
  );
}

/** The credits dashboard is account data — signed-out visitors see the gate. */
export default function CreditsDashboard() {
  return (
    <RequireSession tool="The credits dashboard">
      <CreditsDashboardInner />
    </RequireSession>
  );
}

