"use client";

/**
 * Live scholarships board — the end of the `/scholarships` dead end.
 *
 * Renders the engine's sourced programmes (`GET /scholarships`) as
 * clickable cards with country / level / funding filters and honest
 * deadline wording (unknown stays unknown — never invented). No
 * session is required or requested. Every card links the official
 * programme page and offers the per-programme calendar export.
 */

import { useCallback, useRef, useState } from "react";

import { ENGINE, engineError } from "../../lib/engine";
import { useInitialLoad } from "../../lib/useInitialLoad";

type Scholarship = {
  id: string;
  name: string;
  provider: string;
  country: string;
  countries: string[];
  level: string;
  funding: string;
  window_close: string | null;
  url: string;
  basis: string;
};

const COUNTRIES = ["All", "GB", "DE", "IE", "SE", "CA", "AU", "NZ", "JP", "US"];
const LEVELS = ["All", "masters", "phd", "any"];
const FUNDING = ["All", "fully_funded", "varies"];

const input =
  "mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100";
const tab = (active: boolean) =>
  active
    ? "rounded-full bg-black px-3 py-1 text-xs font-medium text-white dark:bg-white dark:text-black"
    : "rounded-full border border-black/10 px-3 py-1 text-xs font-medium text-zinc-600 hover:border-black/40 dark:border-white/15 dark:text-zinc-300 dark:hover:border-white/40";

function deadlineText(windowClose: string | null): string {
  if (!windowClose) return "Deadline varies — check the official page";
  return `Closes ${windowClose}`;
}

export default function ScholarshipsBoard() {
  const [country, setCountry] = useState("All");
  const [level, setLevel] = useState("All");
  const [funding, setFunding] = useState("All");
  const [rows, setRows] = useState<Scholarship[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  // Mount-only initial fetch, fired through the same loader as every
  // user interaction — the shared hook guarantees exactly one run.
  const didLoadRef = useRef(true);

  const load = useCallback(async (c: string, l: string, f: string) => {
    setBusy(true);
    setError("");
    try {
      const query = new URLSearchParams();
      if (c !== "All") query.set("country", c);
      if (l !== "All") query.set("level", l);
      if (f !== "All") query.set("funding", f);
      const response = await fetch(`${ENGINE}/scholarships?${query.toString()}`);
      const data = await response.json();
      if (!response.ok) {
        setError(engineError(data, response.status));
        setRows([]);
        setTotal(0);
        return;
      }
      const list: Scholarship[] = Array.isArray(data.scholarships) ? data.scholarships : [];
      setRows(list);
      setTotal(typeof data.total === "number" ? data.total : 0);
    } catch {
      setError(`Could not reach the engine at ${ENGINE}.`);
      setRows([]);
      setTotal(0);
    } finally {
      setBusy(false);
    }
  }, []);

  useInitialLoad(didLoadRef, load, country, level, funding);

  function refilter(next: { c?: string; l?: string; f?: string }) {
    const c = next.c ?? country;
    const l = next.l ?? level;
    const f = next.f ?? funding;
    setCountry(c);
    setLevel(l);
    setFunding(f);
    void load(c, l, f);
  }

  return (
    <section aria-label="Live funded scholarships" className="mt-10">
      <h2 className="text-xl font-semibold tracking-tight text-black dark:text-zinc-50">
        Live programmes, sourced from official pages
      </h2>
      <p className="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400" role="status">
        {busy ? "Loading the live programmes…" : `${total} programme${total === 1 ? "" : "s"}`}
      </p>

      <div className="mt-4">
        <p className="text-xs font-medium text-zinc-500">Country</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {COUNTRIES.map((c) => (
            <button key={c} type="button" onClick={() => refilter({ c })} className={tab(country === c)}>
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="text-xs font-medium text-zinc-500">
          Degree level
          <select value={level} onChange={(e) => refilter({ l: e.target.value })} className={input}>
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {l === "All" ? "Any level" : l}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs font-medium text-zinc-500">
          Funding
          <select value={funding} onChange={(e) => refilter({ f: e.target.value })} className={input}>
            {FUNDING.map((f) => (
              <option key={f} value={f}>
                {f === "All" ? "Any funding" : f.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
        >
          {error}
        </p>
      ) : null}

      {rows.length === 0 && !busy && !error ? (
        <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          No programmes match these filters yet — try another country or funding type.
        </p>
      ) : null}

      <ul className="mt-6 flex flex-col gap-3">
        {rows.map((row) => (
          <li
            key={row.id}
            className="rounded-xl border border-black/10 bg-white p-4 dark:border-white/10 dark:bg-zinc-950"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-black dark:text-zinc-100">{row.name}</h3>
                <p className="mt-0.5 text-xs text-zinc-500">
                  {row.provider}
                  {row.country ? ` · ${row.country}` : ""}
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                {row.funding.replace(/_/g, " ")}
              </span>
            </div>
            <p className="mt-2 text-xs leading-5 text-zinc-600 dark:text-zinc-400">
              {deadlineText(row.window_close)} · {row.level}
            </p>
            {row.basis ? (
              <p className="mt-1 text-[11px] leading-5 text-zinc-500">{row.basis}</p>
            ) : null}
            <div className="mt-3 flex flex-wrap items-center gap-3">
              {row.url ? (
                <a
                  href={row.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-medium text-black underline hover:text-zinc-600 dark:text-zinc-100"
                >
                  Official page →
                </a>
              ) : null}
              <a
                href={`${ENGINE}/scholarships/${encodeURIComponent(row.id)}/ics`}
                className="text-xs font-medium text-zinc-600 underline hover:text-black dark:text-zinc-400 dark:hover:text-zinc-100"
              >
                Add deadline to calendar
              </a>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
