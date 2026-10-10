"use client";

/**
 * Waitlist page (task 5.6) — the subscribe half of double opt-in.
 *
 * The engine stores the address as `pending` and queues a confirmation
 * message; nothing is confirmed until the emailed token is redeemed, and
 * this page never claims otherwise.
 */

import { useEffect, useState } from "react";

const ENGINE = process.env.NEXT_PUBLIC_ENGINE_URL || "http://localhost:8000";

export default function WaitlistPage() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "pending" | "confirmed" | "error">("idle");
  const [message, setMessage] = useState("");
  const [stats, setStats] = useState<{ confirmed_count: number } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch(`${ENGINE}/waitlist/stats`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && setStats(data))
      .catch(() => setStats(null)); // social proof is optional; errors stay silent here
  }, []);

  async function subscribe(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`${ENGINE}/waitlist/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await response.json();
      if (!response.ok) {
        setState("error");
        setMessage(data?.detail?.message || `Subscription failed (${response.status}).`);
        return;
      }
      if (data.status === "confirmed") {
        setState("confirmed");
        setMessage("This address is already confirmed on the waitlist.");
      } else {
        setState("pending");
        setMessage(
          "Almost there — a confirmation link is on its way. You're only on " +
            "the list once you click it (double opt-in)."
        );
      }
    } catch {
      setState("error");
      setMessage(`Engine unreachable at ${ENGINE} — set NEXT_PUBLIC_ENGINE_URL.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Join the Vantia waitlist
        </h1>
        <p className="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400">
          Launching soon: visa-sponsored jobs, funded scholarships, ATS scoring
          and application tools.
          {stats ? ` ${stats.confirmed_count} already confirmed.` : ""}
        </p>

        <form onSubmit={subscribe} className="mt-8 flex flex-col gap-3">
          <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300"
          >
            {busy ? "Joining…" : "Join the waitlist"}
          </button>
        </form>

        {message ? (
          <p
            role="status"
            className={
              state === "error"
                ? "mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
                : "mt-6 rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300"
            }
          >
            {message}
          </p>
        ) : null}

        <p className="mt-8 text-xs text-zinc-500">
          Double opt-in: we never add an address that hasn&apos;t confirmed.
          Until an email provider is connected at launch, confirmations are
          queued server-side in a reviewable outbox — nothing pretends to
          have been sent.
        </p>
      </main>
    </div>
  );
}
