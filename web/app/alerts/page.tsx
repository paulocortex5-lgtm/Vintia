"use client";

/**
 * Job alerts (task 15.9 §13.4).
 *
 * Lists the user's saved-search alerts with a frequency toggle and a
 * delete action, and a small form to save a new alert (country + role +
 * daily/weekly). Talks to the engine's `GET/POST/DELETE /alerts`.
 */

import { useCallback, useEffect, useState } from "react";
import { loadSession } from "../../lib/engine";

const ENGINE_URL = process.env.NEXT_PUBLIC_ENGINE_URL || "http://localhost:8000";

type Alert = {
  id: string;
  filters: { countries?: string[]; role?: string };
  frequency: "daily" | "weekly";
  active: boolean;
  created_at: string;
};

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [userId, setUserId] = useState("");
  const [error, setError] = useState("");
  const [country, setCountry] = useState("");
  const [role, setRole] = useState("");
  const [frequency, setFrequency] = useState<"daily" | "weekly">("daily");

  const load = useCallback(async () => {
    const session = loadSession();
    const uid = session?.user?.id || "";
    setUserId(uid);
    if (!uid) {
      setError("Sign in to manage your alerts.");
      return;
    }
    try {
      const res = await fetch(`${ENGINE_URL}/alerts?user_id=${encodeURIComponent(uid)}`);
      if (!res.ok) throw new Error(`engine ${res.status}`);
      const data = await res.json();
      setAlerts(data.alerts || []);
      setError("");
    } catch {
      setError(`Could not load alerts from ${ENGINE_URL}.`);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId) return;
    const filters: Record<string, unknown> = {};
    if (country.trim()) filters.countries = [country.trim().toUpperCase()];
    if (role.trim()) filters.role = role.trim();
    await fetch(`${ENGINE_URL}/alerts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, filters, frequency }),
    });
    setCountry("");
    setRole("");
    load();
  };

  const remove = async (id: string) => {
    await fetch(`${ENGINE_URL}/alerts/${id}?user_id=${encodeURIComponent(userId)}`, {
      method: "DELETE",
    });
    load();
  };

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 px-6 py-12 font-sans dark:bg-black">
      <main className="mx-auto w-full max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Job alerts
        </h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Save a search and we email the top new matching jobs each day or week.
        </p>

        {error ? (
          <p
            role="alert"
            className="mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
          >
            {error}
          </p>
        ) : null}

        <form onSubmit={create} className="mt-6 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="block text-xs text-zinc-500">Country (ISO2)</span>
            <input
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              placeholder="CA"
              className="mt-1 w-24 rounded border border-black/10 bg-white px-2 py-1 text-sm dark:border-white/15 dark:bg-zinc-900"
            />
          </label>
          <label className="text-sm">
            <span className="block text-xs text-zinc-500">Role</span>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="Backend Engineer"
              className="mt-1 w-48 rounded border border-black/10 bg-white px-2 py-1 text-sm dark:border-white/15 dark:bg-zinc-900"
            />
          </label>
          <label className="text-sm">
            <span className="block text-xs text-zinc-500">Frequency</span>
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value as "daily" | "weekly")}
              className="mt-1 rounded border border-black/10 bg-white px-2 py-1 text-sm dark:border-white/15 dark:bg-zinc-900"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
            </select>
          </label>
          <button
            type="submit"
            className="rounded-full bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-white dark:text-black dark:hover:bg-zinc-300"
          >
            Save alert
          </button>
        </form>

        <ul className="mt-8 flex flex-col gap-3">
          {alerts.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between rounded-xl border border-black/10 bg-white p-4 dark:border-white/10 dark:bg-zinc-950"
            >
              <div>
                <p className="text-sm font-medium text-black dark:text-zinc-100">
                  {(a.filters.countries || ["All"]).join(", ")} · {a.filters.role || "any role"}
                </p>
                <p className="text-xs text-zinc-500">
                  {a.frequency} digest · created {a.created_at?.slice(0, 10) || "—"}
                </p>
              </div>
              <button
                onClick={() => remove(a.id)}
                className="rounded-full border border-black/10 px-3 py-1 text-xs text-zinc-600 hover:border-red-400 hover:text-red-600 dark:border-white/15 dark:text-zinc-300"
              >
                Delete
              </button>
            </li>
          ))}
          {alerts.length === 0 && !error ? (
            <li className="text-sm text-zinc-400">No alerts yet — save your first search above.</li>
          ) : null}
        </ul>
      </main>
    </div>
  );
}
