"use client";

/**
 * Job recommendations tool (task 15.1) — paste your CV, get the top-20
 * verified jobs ranked by the engine's deterministic match score. Free
 * tier, no credits; results are cached engine-side for 24 hours.
 */

import { useState } from "react";
import { ENGINE, engineError } from "../../../lib/engine";

type RecommendedJob = {
  job_id: string;
  title: string;
  company: string;
  country: string;
  posted_at: string | null;
  apply_url: string;
  link_status: string;
  match_score: number;
  matched_skills: string[];
  rationale: string;
  reliability?: { label: string; tone: "green" | "amber" | "red" | "neutral" };
};

const input =
  "mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100";
const button =
  "rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300";

const COUNTRIES = ["ALL", "GB", "DE", "IE", "SE", "CA", "AU", "NZ", "US"];

function reliabilityBadge(): string {
  return "border border-black/10 text-xs text-zinc-600 dark:text-zinc-400";
}

export default function RecommendedJobs() {
  const [resumeText, setResumeText] = useState("");
  const [country, setCountry] = useState("ALL");
  const [jobs, setJobs] = useState<RecommendedJob[]>([]);
  const [note, setNote] = useState("");
  const [cached, setCached] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  async function load() {
    setBusy(true);
    setError("");
    try {
      const filters = country === "ALL" ? {} : { countries: [country] };
      const response = await fetch(`${ENGINE}/jobs/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_text: resumeText, filters }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(engineError(data, response.status));
        return;
      }
      setJobs(data.jobs ?? []);
      setNote(data.note ?? "");
      setCached(Boolean(data.cached));
      setLoaded(true);
    } catch {
      setError("Could not reach the engine. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-8 rounded-2xl border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-zinc-950">
      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300" htmlFor="cv">
        Paste your CV
      </label>
      <textarea
        id="cv"
        rows={8}
        value={resumeText}
        onChange={(e) => setResumeText(e.target.value)}
        placeholder={"# Jane Doe\nBackend Engineer\n…"}
        className={`${input} mt-1 font-mono`}
      />
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {COUNTRIES.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setCountry(c)}
            className={
              country === c
                ? "rounded-full bg-black px-3 py-1 text-xs font-medium text-white dark:bg-white dark:text-black"
                : "rounded-full border border-black/10 px-3 py-1 text-xs font-medium text-zinc-600 hover:border-black/40 dark:border-white/20 dark:text-zinc-400"
            }
          >
            {c === "ALL" ? "All countries" : c}
          </button>
        ))}
        <button type="button" onClick={load} disabled={busy} className={`${button} ml-auto`}>
          {busy ? "Ranking…" : loaded ? "Re-rank" : "Get recommendations"}
        </button>
      </div>

      {error && <p className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {note && (
        <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          {note}
        </p>
      )}
      {cached && !note && (
        <p className="mt-4 text-xs text-zinc-500">Cached result (24h TTL) — instant response.</p>
      )}

      {!resumeText.trim() && loaded && (
        <p className="mt-4 text-sm text-zinc-600 dark:text-zinc-400">
          Upload your CV (paste a text-based PDF/DOCX export above) to see personalised
          recommendations — until then these are the most recent verified jobs.
        </p>
      )}

      <ul className="mt-6 flex flex-col gap-3">
        {jobs.map((job) => (
          <li
            key={job.job_id}
            className="rounded-xl border border-black/10 p-4 dark:border-white/10"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-black dark:text-zinc-100">
                  {job.title}
                </h3>
                <p className="mt-0.5 text-xs text-zinc-500">
                  {job.company}
                  {job.country ? ` · ${job.country}` : ""}
                  {job.posted_at ? ` · posted ${job.posted_at}` : ""}
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-black px-2.5 py-0.5 text-[11px] font-medium text-white dark:bg-white dark:text-black">
                {Math.round(job.match_score * 100)}% match
              </span>
            </div>
            {job.matched_skills.length > 0 && (
              <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                Matched: {job.matched_skills.join(", ")} — {job.rationale}
              </p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <span className={reliabilityBadge()}>Direct employer link · {job.link_status}</span>
              {job.reliability && (
                <span
                  className={
                    "rounded-full px-2 py-0.5 text-[11px] font-medium " +
                    (job.reliability.tone === "green"
                      ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300"
                      : job.reliability.tone === "amber"
                        ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                        : job.reliability.tone === "red"
                          ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300"
                          : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400")
                  }
                >
                  {job.reliability.label}
                </span>
              )}
              {job.apply_url && job.link_status === "verified" && (
                <a
                  href={job.apply_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-medium text-black underline hover:text-zinc-600 dark:text-zinc-100"
                >
                  Apply →
                </a>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
