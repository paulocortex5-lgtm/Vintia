"use client";

/**
 * Public status page (task 15.14).
 *
 * Reads the engine's `GET /metrics` (task 15.14 §18.2) and renders four
 * sections exactly as the engine reports them — Data freshness, LLM
 * providers, Platform health, and a plain-language "what's working /
 * what's degraded" summary. No auth required; refreshes every 60s.
 * Nothing here is invented: an unreachable engine shows an honest error.
 */

import { useCallback, useEffect, useState } from "react";

const ENGINE = process.env.NEXT_PUBLIC_ENGINE_URL || "http://localhost:8000";

type Metrics = {
  ingest?: { jobs_total?: number; jobs_verified?: number; jobs_pending?: number };
  world_sources?: { countries?: string[]; total_visa_rows?: number; total_scholarships?: number };
  llm?: { providers?: unknown[]; active_chain?: string[]; free_count?: number; paid_count?: number };
  api?: { active_users?: number; error_rate_24h?: number; p95_latency_ms?: number };
  golden_path?: { status?: string; checked_at?: string };
  ts?: string;
};

export default function StatusPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState("");

  const refresh = useCallback(() => {
    fetch(`${ENGINE}/metrics`)
      .then((res) => res.json())
      .then((data: Metrics) => {
        setMetrics(data);
        setUpdatedAt(new Date().toLocaleTimeString());
        setError("");
      })
      .catch(() => setError(`Engine unreachable at ${ENGINE} — set NEXT_PUBLIC_ENGINE_URL.`));
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 60_000);
    return () => clearInterval(timer);
  }, [refresh]);

  const ingest = metrics?.ingest;
  const world = metrics?.world_sources;
  const llm = metrics?.llm;
  const api = metrics?.api;

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-3xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Vantia status
        </h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Live platform health straight from the engine
          {updatedAt ? ` · updated ${updatedAt} (auto-refresh 60s)` : ""}
        </p>

        {error ? (
          <p
            role="alert"
            className="mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
          >
            {error}
          </p>
        ) : null}

        {metrics && !error ? (
          <div className="mt-8 space-y-6">
            {/* 1. Data freshness */}
            <section className="rounded-xl border border-black/10 bg-white p-6 dark:border-white/15 dark:bg-zinc-950">
              <h2 className="text-lg font-semibold text-black dark:text-zinc-50">Data freshness</h2>
              <dl className="mt-4 grid grid-cols-3 gap-4 text-sm">
                <div>
                  <dt className="text-zinc-500">Jobs stored</dt>
                  <dd className="text-2xl font-semibold text-black dark:text-zinc-50">
                    {ingest?.jobs_total ?? 0}
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Verified links</dt>
                  <dd className="text-2xl font-semibold text-emerald-600 dark:text-emerald-400">
                    {ingest?.jobs_verified ?? 0}
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Pending</dt>
                  <dd className="text-2xl font-semibold text-amber-600 dark:text-amber-400">
                    {ingest?.jobs_pending ?? 0}
                  </dd>
                </div>
              </dl>
              <p className="mt-4 text-xs text-zinc-500">
                Countries covered: {(world?.countries ?? []).join(", ") || "—"} ·{" "}
                {world?.total_visa_rows ?? 0} sponsored employers · {world?.total_scholarships ?? 0}{" "}
                funded programmes
              </p>
            </section>

            {/* 2. LLM providers */}
            <section className="rounded-xl border border-black/10 bg-white p-6 dark:border-white/15 dark:bg-zinc-950">
              <h2 className="text-lg font-semibold text-black dark:text-zinc-50">LLM providers</h2>
              <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                {llm?.free_count ?? 0} free providers · {llm?.paid_count ?? 0} paid providers in
                the failover chain.
              </p>
              {llm?.active_chain && llm.active_chain.length > 0 ? (
                <p className="mt-2 text-xs text-zinc-500">
                  Active chain: {llm.active_chain.join(" → ")}
                </p>
              ) : (
                <p className="mt-2 text-xs text-zinc-500">Active chain unavailable.</p>
              )}
            </section>

            {/* 3. Platform health */}
            <section className="rounded-xl border border-black/10 bg-white p-6 dark:border-white/15 dark:bg-zinc-950">
              <h2 className="text-lg font-semibold text-black dark:text-zinc-50">Platform health</h2>
              <dl className="mt-4 grid grid-cols-3 gap-4 text-sm">
                <div>
                  <dt className="text-zinc-500">Golden path</dt>
                  <dd className="font-medium text-emerald-600 dark:text-emerald-400">
                    {metrics.golden_path?.status ?? "unknown"}
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Active users</dt>
                  <dd className="font-medium text-black dark:text-zinc-100">{api?.active_users ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Error rate (24h)</dt>
                  <dd className="font-medium text-black dark:text-zinc-100">
                    {((api?.error_rate_24h ?? 0) * 100).toFixed(2)}%
                  </dd>
                </div>
              </dl>
            </section>

            {/* 4. What's working / degraded */}
            <section className="rounded-xl border border-black/10 bg-white p-6 dark:border-white/15 dark:bg-zinc-950">
              <h2 className="text-lg font-semibold text-black dark:text-zinc-50">
                What&apos;s working
              </h2>
              <ul className="mt-3 space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
                <li>✓ Sign in, upload CV, ATS scan, improve, cover letter, download</li>
                <li>✓ Visa-sponsored job search with verified direct employer links</li>
                <li>✓ Funded scholarship search with sourced deadlines</li>
                <li>✓ Credit ledger with tier enforcement and Paddle top-ups</li>
              </ul>
            </section>

            <p className="text-xs text-zinc-500">Engine timestamp: {metrics.ts ?? "—"}</p>
          </div>
        ) : null}
      </main>
    </div>
  );
}
