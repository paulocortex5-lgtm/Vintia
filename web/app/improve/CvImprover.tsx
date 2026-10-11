"use client";

/**
 * CV improver (task 13.3) — paste your resume, get fact-preserving edits
 * ranked by impact plus the rebuilt full CV. Deterministic ship layer:
 * identity fields are re-stamped from your text, never model-owned.
 */

import { useState } from "react";
import { ENGINE, engineError } from "../../lib/engine";

type Improvement = {
  category: string;
  section?: string;
  original_text: string;
  improved_text: string;
  reason: string;
  impact?: string;
};
type Result = {
  improvement: {
    original_cv_id: string;
    improvements: Improvement[];
    improved_cv: string;
    summary: { total_improvements: number; high_impact_count: number };
  };
  provider: string;
};

const input =
  "mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100";
const label = "text-sm font-medium text-zinc-700 dark:text-zinc-300";
const button =
  "rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300";

export default function CvImprover() {
  const [resumeText, setResumeText] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function improve(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${ENGINE}/improve/cv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_text: resumeText, job_title: jobTitle, job_description: jobDescription }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(engineError(data, response.status));
        return;
      }
      setResult(data as Result);
    } catch {
      setError(`Engine unreachable at ${ENGINE} — check NEXT_PUBLIC_ENGINE_URL.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-10 rounded-2xl border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-zinc-950">
      <form onSubmit={improve} className="flex flex-col gap-3">
        <label className={label}>
          Your current CV (markdown or plain text)
          <textarea
            required
            rows={10}
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            placeholder={"# Jane Doe\nBackend Engineer\n…"}
            className={`${input} font-mono`}
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className={label}>
            Target job title (optional)
            <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} className={input} placeholder="Backend Engineer" />
          </label>
          <label className={label}>
            Target job description (optional)
            <input value={jobDescription} onChange={(e) => setJobDescription(e.target.value)} className={input} placeholder="Paste the posting for keyword mirroring" />
          </label>
        </div>
        <button type="submit" disabled={busy} className={button}>
          {busy ? "Improving…" : "Improve my CV"}
        </button>
      </form>

      {error ? (
        <p role="status" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      ) : null}

      {result ? (
        <div className="mt-6 flex flex-col gap-4">
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {result.improvement.summary.total_improvements} edits proposed,{" "}
            {result.improvement.summary.high_impact_count} high impact · provider:{" "}
            {result.provider}
          </p>
          <ul className="flex flex-col gap-3">
            {result.improvement.improvements.map((item, index) => (
              <li key={index} className="rounded-lg border border-black/10 p-3 text-sm dark:border-white/10">
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-black/5 px-2 py-0.5 text-xs capitalize dark:bg-white/10">
                    {item.category.replace(/_/g, " ")}
                  </span>
                  {item.impact ? <span className="text-xs text-zinc-500">{item.impact} impact</span> : null}
                </div>
                <p className="mt-2 text-zinc-500 line-through">{item.original_text}</p>
                <p className="mt-1 text-zinc-800 dark:text-zinc-200">{item.improved_text}</p>
                <p className="mt-1 text-xs text-zinc-500">{item.reason}</p>
              </li>
            ))}
          </ul>
          <details className="rounded-lg border border-black/10 p-3 dark:border-white/10">
            <summary className="cursor-pointer text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Full improved CV
            </summary>
            <pre className="mt-2 whitespace-pre-wrap font-mono text-xs text-zinc-700 dark:text-zinc-300">
              {result.improvement.improved_cv}
            </pre>
          </details>
        </div>
      ) : null}
    </section>
  );
}

