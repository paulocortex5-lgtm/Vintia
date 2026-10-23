"use client";

/**
 * Hidden admin console (invoked only by typing /admin — never linked).
 *
 * Every call carries the admin token as `Authorization: Bearer …`; the
 * engine is fail-closed, so a missing key (503 admin_not_configured),
 * a wrong key (403 admin_forbidden) and an unreachable engine are each
 * shown verbatim — nothing here fakes a successful settings change.
 * Env vars that mask a saved value are rendered as warnings, matching
 * the engine's honesty reporting.
 */

import { useCallback, useEffect, useState } from "react";

import { ENGINE, engineError } from "../../lib/engine";

type TierInfo = {
  tokens: number;
  state_tokens: number | null;
  env_override: { env: string; value: string; state_value: unknown }[];
  env_value?: string | null;
};
type Overview = {
  flags: Record<string, boolean>;
  flags_env: { env: string; value: string }[];
  tiers: Record<string, TierInfo>;
  credits_enabled: boolean;
  token_costs: Record<string, number>;
  paid_usage: {
    enabled: boolean;
    profile: string;
    env_override: { env: string; value: string }[];
  };
  ledger: {
    user_count: number;
    total_balance: number;
    by_tier: Record<string, number>;
    updated_at: string | null;
  };
  ts: string;
};
type UserCredits = {
  user_id: string;
  balance: number;
  tier: string;
  monthly_allowance: number;
  summary: {
    balance: number;
    entry_count: number;
    total_earned: number;
    total_spent: number;
    last_entry_ts: string | null;
  };
  recent_entries: {
    ts: string;
    kind: string;
    amount: number;
    balance_after: number;
    meta?: Record<string, unknown>;
  }[];
};

const input =
  "mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100";
const label = "text-sm font-medium text-zinc-700 dark:text-zinc-300";
const button =
  "rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300";
const buttonGhost =
  "rounded-full border border-black/20 px-5 py-2 text-sm font-medium text-black hover:bg-black/5 disabled:opacity-50 dark:border-white/30 dark:text-zinc-100 dark:hover:bg-white/10";
const card = "rounded-2xl border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-zinc-950";

const TOKEN_KEY = "vantia_admin_token";
const TIERS = ["free", "pro", "business"] as const;

export default function AdminConsole() {
  const [token, setToken] = useState(() => {
    if (typeof window === "undefined") return "";
    return window.localStorage.getItem(TOKEN_KEY) ?? "";
  });
  const [unlocked, setUnlocked] = useState(false);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Tier allowance edits (controlled inputs seeded from the overview).
  const [tierDraft, setTierDraft] = useState<Record<string, string>>({});

  // Per-user credits tools.
  const [userId, setUserId] = useState("");
  const [userCredits, setUserCredits] = useState<UserCredits | null>(null);
  const [amount, setAmount] = useState("");
  const [grantNote, setGrantNote] = useState("");
  const [userTier, setUserTier] = useState("free");

  const headers = useCallback(
    (extra: Record<string, string> = {}) => ({
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...extra,
    }),
    [token]
  );

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${ENGINE}/admin/overview`, { headers: headers() });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        setUnlocked(false);
        setError(engineError(body, response.status));
        return;
      }
      const data = body as Overview;
      setOverview(data);
      setUnlocked(true);
      setTierDraft(
        Object.fromEntries(
          Object.entries(data.tiers).map(([tier, info]) => [tier, String(info.state_tokens ?? info.tokens)])
        )
      );
    } catch {
      setError(`Engine unreachable at ${ENGINE}.`);
      setUnlocked(false);
    } finally {
      setBusy(false);
    }
  }, [headers]);

  useEffect(() => {
    // `load` updates overview/credits state (setState inside a callback,
    // not directly in this effect body); keep the exhaustive-deps override
    // as the token is the intentional trigger.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (token) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function unlock(e: React.FormEvent) {
    e.preventDefault();
    window.localStorage.setItem(TOKEN_KEY, token);
    void load();
  }

  function lock() {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUnlocked(false);
    setOverview(null);
  }

  async function saveTiers() {
    setBusy(true);
    setNote("");
    setError("");
    try {
      const payload = Object.fromEntries(
        Object.entries(tierDraft)
          .filter(([, value]) => value.trim() !== "")
          .map(([tier, value]) => [`${tier}_tier_tokens`, Number(value)])
      );
      const response = await fetch(`${ENGINE}/admin/tiers`, {
        method: "PUT",
        headers: headers(),
        body: JSON.stringify(payload),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        setError(engineError(body, response.status));
        return;
      }
      const masked = Object.values((body as { tiers: Record<string, TierInfo> }).tiers).flatMap(
        (t) => t.env_override
      );
      setNote(
        masked.length
          ? `Saved, but env vars override state: ${masked.map((m) => m.env).join(", ")}.`
          : "Tier allowances saved."
      );
      await load();
    } catch {
      setError(`Engine unreachable at ${ENGINE}.`);
    } finally {
      setBusy(false);
    }
  }


  async function switchUsage(enabled: boolean) {
    setBusy(true);
    setNote("");
    setError("");
    try {
      const response = await fetch(`${ENGINE}/admin/usage-tier`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ enabled }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        setError(engineError(body, response.status));
        return;
      }
      const result = body as { enabled: boolean; effective_flag: boolean; env_override: { env: string }[] };
      setNote(
        result.env_override.length
          ? `Stored ${result.enabled ? "ON" : "OFF"}, but env overrides apply: ${result.env_override
              .map((m) => m.env)
              .join(", ")}.`
          : `Paid usage tier is now ${result.enabled ? "ON" : "OFF"}.`
      );
      await load();
    } catch {
      setError(`Engine unreachable at ${ENGINE}.`);
    } finally {
      setBusy(false);
    }
  }

  const lookupUser = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!userId.trim()) return;
      setBusy(true);
      setError("");
      try {
        const response = await fetch(
          `${ENGINE}/admin/credits?user_id=${encodeURIComponent(userId.trim())}`,
          { headers: headers() }
        );
        const body = await response.json().catch(() => null);
        if (!response.ok) {
          setError(engineError(body, response.status));
          setUserCredits(null);
          return;
        }
        const data = body as UserCredits;
        setUserCredits(data);
        setUserTier(data.tier);
      } catch {
        setError(`Engine unreachable at ${ENGINE}.`);
      } finally {
        setBusy(false);
      }
    },
    [headers, userId]
  );

  async function applyGrant(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote("");
    setError("");
    try {
      const response = await fetch(`${ENGINE}/admin/credits/grant`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ user_id: userId.trim(), amount: Number(amount), note: grantNote }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        setError(engineError(body, response.status));
        return;
      }
      const result = body as { balance: number };
      setNote(`Applied. New balance: ${result.balance.toLocaleString()} credits.`);
      setAmount("");
      setGrantNote("");
      await lookupUser();
    } catch {
      setError(`Engine unreachable at ${ENGINE}.`);
    } finally {
      setBusy(false);
    }
  }

  async function saveUserTier(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote("");
    setError("");
    try {
      const response = await fetch(`${ENGINE}/admin/users/tier`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ user_id: userId.trim(), tier: userTier }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        setError(engineError(body, response.status));
        return;
      }
      const result = body as { tier: string; monthly_allowance: number };
      setNote(
        `Tier recorded as ${result.tier} (monthly allowance ${result.monthly_allowance.toLocaleString()} tokens).`
      );
      await lookupUser();
    } catch {
      setError(`Engine unreachable at ${ENGINE}.`);
    } finally {
      setBusy(false);
    }
  }


  // ── Token gate (fail-closed on the engine side too) ────────────────
  if (!unlocked) {
    return (
      <section className={`${card} mt-8`}>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Signed in as the admin account — one more factor to go. This panel
          is not listed anywhere; the engine&apos;s admin API additionally
          requires its own key (<code className="font-mono">VANTIA_ADMIN_TOKEN</code>,
          set in the Render dashboard). While that key is unset on the engine,
          every admin request fails closed with <code className="font-mono">503</code>.
        </p>
        <form onSubmit={unlock} className="mt-4 flex flex-col gap-3 sm:flex-row">
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Admin API key"
            className={input}
            autoComplete="off"
          />
          <button type="submit" disabled={busy || !token.trim()} className={button}>
            Unlock
          </button>
        </form>
        {error ? (
          <p
            role="alert"
            className="mt-4 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
          >
            {error}
          </p>
        ) : null}
      </section>
    );
  }

  return (
    <div className="mt-6 flex flex-col gap-6">
      {error ? (
        <p
          role="alert"
          className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
        >
          {error}
        </p>
      ) : null}
      {note ? (
        <p
          role="status"
          className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200"
        >
          {note}
        </p>
      ) : null}

      {/* ── Overview ─────────────────────────────────────────────── */}
      {overview ? (
        <section className={card}>
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-medium text-zinc-500">Platform overview</h2>
            <button
              type="button"
              onClick={lock}
              className="text-xs text-zinc-500 underline hover:text-black dark:hover:text-zinc-300"
            >
              Lock panel
            </button>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-zinc-500">Users</dt>
              <dd className="font-semibold text-black dark:text-zinc-100">
                {overview.ledger.user_count}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Total balance</dt>
              <dd className="font-semibold text-black dark:text-zinc-100">
                {overview.ledger.total_balance.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Credits system</dt>
              <dd className="font-semibold text-black dark:text-zinc-100">
                {overview.credits_enabled ? "enabled" : "disabled"}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Usage tier</dt>
              <dd className="font-semibold text-black dark:text-zinc-100">
                {overview.paid_usage.enabled ? "paid" : "free"}
              </dd>
            </div>
          </dl>
          <ul className="mt-3 flex flex-wrap gap-2 text-xs">
            {Object.entries(overview.flags).map(([name, on]) => (
              <li
                key={name}
                className={`rounded-full px-2.5 py-1 ${
                  on
                    ? "bg-black text-white dark:bg-white dark:text-black"
                    : "bg-black/5 text-zinc-500 dark:bg-white/10 dark:text-zinc-400"
                }`}
              >
                {name}: {on ? "on" : "off"}
              </li>
            ))}
          </ul>
        </section>
      ) : null}


      {/* ── Usage tier switch ────────────────────────────────────── */}
      {overview ? (
        <section className={card}>
          <h2 className="text-sm font-medium text-zinc-500">Paid usage tier</h2>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Stored state: <strong>{overview.paid_usage.enabled ? "paid" : "free"}</strong>{" "}
            (profile <code className="font-mono">{overview.paid_usage.profile || "—"}</code>).
            Free providers are always exhausted before paid ones (R27).
          </p>
          {overview.paid_usage.env_override.length ? (
            <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
              Env override active:{" "}
              {overview.paid_usage.env_override.map((m) => `${m.env}=${m.value}`).join(", ")} — change
              it in Render to make this switch take full effect.
            </p>
          ) : null}
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              disabled={busy}
              onClick={() => switchUsage(false)}
              className={buttonGhost}
            >
              Switch to free
            </button>
            <button type="button" disabled={busy} onClick={() => switchUsage(true)} className={button}>
              Switch to paid
            </button>
          </div>
        </section>
      ) : null}

      {/* ── Tier allowances ──────────────────────────────────────── */}
      {overview ? (
        <section className={card}>
          <h2 className="text-sm font-medium text-zinc-500">
            Usage tier allowances (monthly tokens)
          </h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {TIERS.map((tier) => (
              <div key={tier}>
                <label className={label} htmlFor={`tier-${tier}`}>
                  {tier}
                  {overview.tiers[tier]?.env_value ? " (env-overridden)" : ""}
                </label>
                <input
                  id={`tier-${tier}`}
                  inputMode="numeric"
                  value={tierDraft[tier] ?? ""}
                  onChange={(e) => setTierDraft((prev) => ({ ...prev, [tier]: e.target.value }))}
                  className={input}
                />
                {overview.tiers[tier]?.env_override.length ? (
                  <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                    {overview.tiers[tier].env_override.map((m) => m.env).join(", ")} wins at read
                    time
                  </p>
                ) : null}
              </div>
            ))}
          </div>
          <button type="button" disabled={busy} onClick={saveTiers} className={`${button} mt-4`}>
            Save allowances
          </button>
        </section>
      ) : null}


      {/* ── Per-user credits ─────────────────────────────────────── */}
      <section className={card}>
        <h2 className="text-sm font-medium text-zinc-500">User credits &amp; tier</h2>
        <form onSubmit={lookupUser} className="mt-3 flex flex-col gap-3 sm:flex-row">
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="User id (Supabase sub)"
            className={input}
          />
          <button type="submit" disabled={busy || !userId.trim()} className={buttonGhost}>
            Look up
          </button>
        </form>

        {userCredits ? (
          <div className="mt-4">
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-zinc-500">Balance</dt>
                <dd className="font-semibold text-black dark:text-zinc-100">
                  {userCredits.balance.toLocaleString()}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500">Tier</dt>
                <dd className="font-semibold text-black dark:text-zinc-100">
                  {userCredits.tier}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500">Earned</dt>
                <dd className="font-semibold text-black dark:text-zinc-100">
                  {userCredits.summary.total_earned.toLocaleString()}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500">Spent</dt>
                <dd className="font-semibold text-black dark:text-zinc-100">
                  {userCredits.summary.total_spent.toLocaleString()}
                </dd>
              </div>
            </dl>

            <form onSubmit={applyGrant} className="mt-4 grid gap-3 sm:grid-cols-3">
              <div>
                <label className={label} htmlFor="grant-amount">
                  Credits (+ grant / − adjust)
                </label>
                <input
                  id="grant-amount"
                  inputMode="numeric"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="e.g. 5000 or -500"
                  className={input}
                />
              </div>
              <div>
                <label className={label} htmlFor="grant-note">
                  Note
                </label>
                <input
                  id="grant-note"
                  value={grantNote}
                  onChange={(e) => setGrantNote(e.target.value)}
                  placeholder="why (stored in the ledger)"
                  className={input}
                />
              </div>
              <div className="flex items-end">
                <button type="submit" disabled={busy || !amount.trim()} className={button}>
                  Apply credits
                </button>
              </div>
            </form>

            <form
              onSubmit={saveUserTier}
              className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end"
            >
              <div className="flex-1">
                <label className={label} htmlFor="user-tier">
                  Usage tier (recorded, never inferred)
                </label>
                <select
                  id="user-tier"
                  value={userTier}
                  onChange={(e) => setUserTier(e.target.value)}
                  className={input}
                >
                  {TIERS.map((tier) => (
                    <option key={tier} value={tier}>
                      {tier}
                    </option>
                  ))}
                </select>
              </div>
              <button type="submit" disabled={busy} className={buttonGhost}>
                Record tier
              </button>
            </form>

            {userCredits.recent_entries.length ? (
              <div className="mt-4">
                <h3 className="text-xs font-medium text-zinc-500">Recent ledger entries</h3>
                <ul className="mt-2 flex flex-col gap-1 text-xs">
                  {userCredits.recent_entries
                    .slice(-8)
                    .reverse()
                    .map((entry, index) => (
                      <li
                        key={index}
                        className="flex justify-between text-zinc-600 dark:text-zinc-400"
                      >
                        <span>
                          {entry.kind}
                          {entry.meta && typeof entry.meta.note === "string" && entry.meta.note
                            ? ` — ${entry.meta.note}`
                            : ""}{" "}
                          <span className="text-zinc-400">{entry.ts.slice(0, 19).replace("T", " ")}</span>
                        </span>
                        <span className="font-mono">
                          {entry.amount > 0 ? "+" : ""}
                          {entry.amount.toLocaleString()} → {entry.balance_after.toLocaleString()}
                        </span>
                      </li>
                    ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
