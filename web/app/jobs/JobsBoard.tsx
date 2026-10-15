"use client";

/**
 * Live jobs board — the end of the `/jobs` dead end.
 *
 * Renders the engine's live store (`GET /jobs`) as clickable cards with
 * a country filter, a role search and an honest empty/error state. No
 * session is required or requested: this is the top-of-funnel browse
 * surface. Honours an initial `?country=` from the pipeline country
 * tabs. Never invents a listing — everything comes from the engine.
 */

import { useCallback, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ENGINE, engineError } from "../../lib/engine";
import { useInitialJobsLoad } from "../../lib/useInitialLoad";

type Job = {
  job_id: string;
  title: string;
  company: string;
  country: string;
  location: string;
  posted_at: string | null;
  apply_url: string;
  link_status: string;
  visa_sponsorship: boolean | null;
  description: string;
};

const COUNTRIES = ["All", "GB", "DE", "IE", "SE", "CA", "AU", "NZ", "JP", "US"];

const input =
  "mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100";
const tab = (active: boolean) =>
  active
    ? "rounded-full bg-black px-3 py-1 text-xs font-medium text-white dark:bg-white dark:text-black"
    : "rounded-full border border-black/10 px-3 py-1 text-xs font-medium text-zinc-600 hover:border-black/40 dark:border-white/15 dark:text-zinc-300 dark:hover:border-white/40";

export default function JobsBoard() {
  const params = useSearchParams();
  const urlCountry = (params.get("country") || "").toUpperCase();
  const start = COUNTRIES.includes(urlCountry) ? urlCountry : "All";
  const [country, setCountry] = useState(start);
  const [role, setRole] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  const load = useCallback(async (nextCountry: string, nextRole: string) => {
    setBusy(true);
    setError("");
    try {
      const query = new URLSearchParams();
      if (nextCountry !== "All") query.set("country", nextCountry);
      if (nextRole.trim()) query.set("role", nextRole.trim());
      query.set("limit", "100");
      const response = await fetch(`${ENGINE}/jobs?${query.toString()}`);
      const data = await response.json();
      if (!response.ok) {
        setError(engineError(data, response.status));
        setJobs([]);
        setTotal(0);
        return;
      }
      const list: Job[] = Array.isArray(data.jobs) ? data.jobs : [];
      setJobs(list);
      setTotal(typeof data.total === "number" ? data.total : 0);
      setNote(
        list.length === 0
          ? "No verified postings match these filters yet — try another country or role."
          : ""
      );
    } catch {
      setError(`Could not reach the engine at ${ENGINE}.`);
      setJobs([]);
      setTotal(0);
    } finally {
      setBusy(false);
    }
  }, []);

  // The country is seeded from `?country=` (pipeline country tabs) via
  // initial state above; the single mount-only fetch runs through the
  // shared hook.
  const didLoadRef = useRef(true);

  useInitialJobsLoad(didLoadRef, load, start);

  function pick(next: string) {
    setCountry(next);
    void load(next, role);
  }

  function search(e: React.FormEvent) {
    e.preventDefault();
    void load(country, role);
  }

  return (
    <section aria-label="Live visa-sponsored jobs" className="mt-10">
      <h2 className="text-xl font-semibold tracking-tight text-black dark:text-zinc-50">
        Live jobs, verified before you read them
      </h2>
      <p className="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400" role="status">
        {busy
          ? "Loading the live pool…"
          : `${total} verified posting${total === 1 ? "" : "s"}${country === "All" ? "" : ` in ${country}`}`}
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {COUNTRIES.map((c) => (
          <button key={c} type="button" onClick={() => pick(c)} className={tab(country === c)}>
            {c}
          </button>
        ))}
      </div>

      <form onSubmit={search} className="mt-4 flex gap-2">
        <input
          value={role}
          onChange={(e) => setRole(e.target.value)}
          placeholder="Filter by role — e.g. engineer"
          aria-label="Filter jobs by role"
          className={input}
        />
        <button
          type="submit"
          disabled={busy}
          className="shrink-0 rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300"
        >
          {busy ? "…" : "Search"}
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
      {note && !error ? (
        <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          {note}
        </p>
      ) : null}

      <ul className="mt-6 flex flex-col gap-3">
        {jobs.map((job) => (
          <li
            key={job.job_id}
            className="rounded-xl border border-black/10 bg-white p-4 dark:border-white/10 dark:bg-zinc-950"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-black dark:text-zinc-100">{job.title}</h3>
                <p className="mt-0.5 text-xs text-zinc-500">
                  {job.company}
                  {job.country ? ` · ${job.country}` : ""}
                  {job.location && job.location !== job.country ? ` · ${job.location}` : ""}
                </p>
              </div>
              {job.visa_sponsorship ? (
                <span className="shrink-0 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  Visa sponsorship
                </span>
              ) : null}
            </div>
            {job.description ? (
              <p className="mt-2 text-xs leading-5 text-zinc-600 dark:text-zinc-400">
                {job.description}
              </p>
            ) : null}
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <span className="rounded-full border border-black/10 px-2 py-0.5 text-[11px] text-zinc-600 dark:border-white/15 dark:text-zinc-400">
                Direct employer link · {job.link_status || "verified"}
              </span>
              {job.apply_url ? (
                <a
                  href={job.apply_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-medium text-black underline hover:text-zinc-600 dark:text-zinc-100"
                >
                  Apply →
                </a>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
