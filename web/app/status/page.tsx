"use client";

/**
 * Public status page (task 6.2).
 *
 * Reads the engine's `GET /status` (task 9.4) and renders build progress
 * exactly as the engine reports it — no invented numbers, and an explicit,
 * honest message when the engine cannot be reached.
 */

import { useCallback, useEffect, useState } from "react";

type Status = {
  initialised: boolean;
  total: number;
  complete: number;
  pending: number;
  blocked: number;
  next_task: string | null;
  run_count: number;
  last_completed_task: string | null;
  readiness_pct: number;
  ts: string;
};

const ENGINE = process.env.NEXT_PUBLIC_ENGINE_URL || "http://localhost:8000";

export default function StatusPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState("");

  const refresh = useCallback(() => {
    fetch(`${ENGINE}/status`)
      .then((res) => res.json())
      .then((data) => {
        setStatus(data);
        setUpdatedAt(new Date().toLocaleTimeString());
        setError("");
      })
      .catch(() => {
        setError(`Engine unreachable at ${ENGINE} — set NEXT_PUBLIC_ENGINE_URL.`);
      });
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 30_000);
    return () => clearInterval(timer);
  }, [refresh]);

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Vantia status
        </h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Live build progress straight from the engine
          {updatedAt ? ` · updated ${updatedAt} (auto-refresh 30s)` : ""}
        </p>

        {error ? (
          <p
            role="alert"
            className="mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
          >
            {error}
          </p>
        ) : null}

        {status && !error ? (
          <section className="mt-8 rounded-xl border border-black/10 bg-white p-6 dark:border-white/15 dark:bg-zinc-950">
            <div className="flex items-baseline justify-between">
              <span className="text-5xl font-semibold text-black dark:text-zinc-50">
                {status.readiness_pct}%
              </span>
              <span className="text-sm text-zinc-500">
                {status.complete}/{status.total} tasks
              </span>
            </div>
            <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
              <div
                className="h-2 rounded-full bg-emerald-500"
                style={{ width: `${status.readiness_pct}%` }}
              />
            </div>
            <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-zinc-500">Pending</dt>
                <dd className="font-medium text-black dark:text-zinc-100">{status.pending}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Blocked</dt>
                <dd className="font-medium text-black dark:text-zinc-100">{status.blocked}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Runs</dt>
                <dd className="font-medium text-black dark:text-zinc-100">{status.run_count}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Next task</dt>
                <dd className="font-medium text-black dark:text-zinc-100">
                  {status.next_task ?? "—"}
                </dd>
              </div>
              <div className="col-span-2 flex justify-between">
                <dt className="text-zinc-500">Last completed</dt>
                <dd className="font-medium text-black dark:text-zinc-100">
                  {status.last_completed_task ?? "—"}
                </dd>
              </div>
              <div className="col-span-2 flex justify-between">
                <dt className="text-zinc-500">Engine timestamp</dt>
                <dd className="font-mono text-xs text-black dark:text-zinc-300">{status.ts}</dd>
              </div>
            </dl>
            <p className="mt-6 text-xs text-zinc-500">
              {status.initialised
                ? "Data is read live from the engine; nothing on this page is cached or hand-written."
                : "The engine has no initialised state yet (bootstrap not run)."}
            </p>
          </section>
        ) : null}
      </main>
    </div>
  );
}
