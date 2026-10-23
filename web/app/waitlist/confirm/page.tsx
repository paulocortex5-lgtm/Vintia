"use client";

/**
 * Waitlist confirmation page (task 5.6) — the redeem half of double opt-in.
 *
 * Reads `?token=` from the URL (no useSearchParams, so the page stays
 * statically buildable) and redeems it against the engine. Invalid tokens
 * get an honest error, never a fake success.
 */

import { useEffect, useState } from "react";

const ENGINE = process.env.NEXT_PUBLIC_ENGINE_URL || "http://localhost:8000";

export default function WaitlistConfirmPage() {
  const [state, setState] = useState<"checking" | "confirmed" | "error">("checking");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token") || "";
    if (!token) {
      // Token comes from the URL (client-only), so this initial state is set
      // after mount rather than during render.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState("error");
      setMessage("Missing confirmation token — open the link from your email.");
      return;
    }
    fetch(`${ENGINE}/waitlist/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) {
          setState("error");
          setMessage(data?.detail?.message || `Confirmation failed (${res.status}).`);
          return;
        }
        setState("confirmed");
        setMessage(
          data.already
            ? "This address was already confirmed — you're on the list."
            : "You're on the list. We'll email when Vantia launches."
        );
      })
      .catch(() => {
        setState("error");
        setMessage(`Engine unreachable at ${ENGINE} — set NEXT_PUBLIC_ENGINE_URL.`);
      });
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Confirm your waitlist signup
        </h1>
        <p
          role="status"
          className={
            state === "error"
              ? "mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
              : "mt-6 rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300"
          }
        >
          {state === "checking" ? "Checking your token…" : message}
        </p>
      </main>
    </div>
  );
}
