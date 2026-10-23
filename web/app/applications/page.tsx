"use client";

/**
 * Application tracker (task 15.8 §12.3).
 *
 * A kanban board: five columns (Applied, Interview, Offer, Rejected,
 * Withdrawn). Each card shows the job title, company and applied date,
 * snapshotted when the application was tracked. Move a card by picking a
 * new status — it persists to the engine's `PATCH /applications/{id}`.
 * No auth SDK: the signed-in user id is read from the stored session.
 */

import { useCallback, useEffect, useState } from "react";
import { loadSession } from "../../lib/engine";

const ENGINE_URL = process.env.NEXT_PUBLIC_ENGINE_URL || "http://localhost:8000";

type Application = {
  id: string;
  job_id: string;
  status: string;
  notes: string;
  applied_at: string;
  updated_at: string;
  job_snapshot: { title?: string; company?: string; country?: string; apply_url?: string };
};

const COLUMNS = ["applied", "interview", "offer", "rejected", "withdrawn"];
const LABEL: Record<string, string> = {
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export default function ApplicationsPage() {
  const [apps, setApps] = useState<Application[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [userId, setUserId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const session = loadSession();
    const uid = session?.user?.id || "";
    setUserId(uid);
    if (!uid) {
      setError("Sign in to track your applications.");
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${ENGINE_URL}/applications?user_id=${encodeURIComponent(uid)}`);
      if (!res.ok) throw new Error(`engine ${res.status}`);
      const data = await res.json();
      setApps(data.applications || []);
      setCounts(data.counts || {});
      setError("");
    } catch {
      setError(`Could not load applications from ${ENGINE_URL}.`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // `load` updates application state from the engine (setState inside its
    // body, not directly in this effect body).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const move = async (app: Application, status: string) => {
    if (status === app.status) return;
    await fetch(`${ENGINE_URL}/applications/${app.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, status }),
    });
    load();
  };

  const byColumn = (col: string) => apps.filter((a) => a.status === col);

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 px-6 py-12 font-sans dark:bg-black">
      <main className="mx-auto w-full max-w-6xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Application tracker
        </h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          {apps.length} application{apps.length === 1 ? "" : "s"} tracked. Move a card
          between columns to update its status.
        </p>

        {error ? (
          <p
            role="alert"
            className="mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
          >
            {error}
          </p>
        ) : null}

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {COLUMNS.map((col) => (
            <section key={col} className="rounded-xl bg-black/[0.03] p-3 dark:bg-white/5">
              <h2 className="flex items-center justify-between px-1 text-sm font-semibold text-black dark:text-zinc-100">
                {LABEL[col]}
                <span className="rounded-full bg-black/10 px-2 py-0.5 text-xs text-zinc-600 dark:bg-white/10 dark:text-zinc-300">
                  {counts[col] ?? byColumn(col).length}
                </span>
              </h2>
              <ul className="mt-3 flex flex-col gap-2">
                {byColumn(col).map((app) => (
                  <li
                    key={app.id}
                    className="rounded-lg border border-black/10 bg-white p-3 dark:border-white/10 dark:bg-zinc-950"
                  >
                    <p className="text-sm font-medium text-black dark:text-zinc-100">
                      {app.job_snapshot?.title || "Untitled role"}
                    </p>
                    <p className="text-xs text-zinc-500">
                      {app.job_snapshot?.company || "—"}
                      {app.job_snapshot?.country ? ` · ${app.job_snapshot.country}` : ""}
                    </p>
                    <p className="mt-1 text-[11px] text-zinc-400">
                      Applied {app.applied_at?.slice(0, 10) || "—"}
                    </p>
                    <label className="mt-2 block text-[11px] text-zinc-500">
                      <span className="sr-only">Move to</span>
                      <select
                        value={app.status}
                        onChange={(e) => move(app, e.target.value)}
                        className="mt-1 w-full rounded border border-black/10 bg-white px-2 py-1 text-xs dark:border-white/15 dark:bg-zinc-900"
                      >
                        {COLUMNS.map((c) => (
                          <option key={c} value={c}>
                            {LABEL[c]}
                          </option>
                        ))}
                      </select>
                    </label>
                  </li>
                ))}
                {byColumn(col).length === 0 && !loading ? (
                  <li className="px-1 py-2 text-xs text-zinc-400">No applications</li>
                ) : null}
              </ul>
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}
