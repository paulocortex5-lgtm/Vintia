"use client";

/**
 * ATS scanner (task 13.2) — upload a file or paste your resume, get the
 * same twelve-point report the pipeline runs. Deterministic: no LLM key
 * touches this path, and an unparseable upload shows the engine's honest
 * error instead of an empty 0/100.
 */

import { useState } from "react";
import { ENGINE, engineError } from "../../lib/engine";

type CategoryScore = { score: number; max_score: number; suggestions?: string[] };
type Report = {
  overall_score: number;
  category_scores: Record<string, CategoryScore>;
  missing_keywords: string[];
  matched_keywords?: string[];
};

const input =
  "mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100";
const label = "text-sm font-medium text-zinc-700 dark:text-zinc-300";
const button =
  "rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300";

export default function AtsScanner() {
  const [mode, setMode] = useState<"upload" | "paste">("paste");
  const [resumeText, setResumeText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [jobTitle, setJobTitle] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [jobLocation, setJobLocation] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function scan(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setReport(null);
    try {
      let response: Response;
      if (mode === "upload") {
        if (!file) {
          setError("Choose a resume file first (pdf, docx, txt or md).");
          setBusy(false);
          return;
        }
        const form = new FormData();
        form.append("file", file);
        form.append("job_title", jobTitle);
        form.append("job_description", jobDescription);
        form.append("job_location", jobLocation);
        response = await fetch(`${ENGINE}/ats/upload`, { method: "POST", body: form });
      } else {
        response = await fetch(`${ENGINE}/ats/score`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resume_text: resumeText,
            job_title: jobTitle,
            job_description: jobDescription,
            job_location: jobLocation,
          }),
        });
      }
      const data = await response.json();
      if (!response.ok) {
        setError(engineError(data, response.status));
        return;
      }
      setReport(data.report as Report);
    } catch {
      setError(`Engine unreachable at ${ENGINE} — check NEXT_PUBLIC_ENGINE_URL.`);
    } finally {
      setBusy(false);
    }
  }

  const modeButton = (active: boolean) =>
    `rounded-full px-4 py-1.5 text-xs font-medium ${
      active
        ? "bg-black text-white dark:bg-white dark:text-black"
        : "border border-black/10 text-zinc-700 dark:border-white/20 dark:text-zinc-300"
    }`;

  return (
    <section className="mt-10 rounded-2xl border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-zinc-950">
      <div className="flex gap-2">
        <button type="button" onClick={() => setMode("paste")} className={modeButton(mode === "paste")}>
          Paste resume
        </button>
        <button type="button" onClick={() => setMode("upload")} className={modeButton(mode === "upload")}>
          Upload file
        </button>
      </div>

      <form onSubmit={scan} className="mt-4 flex flex-col gap-3">
        {mode === "paste" ? (
          <label className={label}>
            Your resume (markdown or plain text)
            <textarea
              required
              rows={8}
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder={"# Jane Doe\nBackend Engineer\n…"}
              className={`${input} font-mono`}
            />
          </label>
        ) : (
          <label className={label}>
            Resume file (pdf, docx, txt, md)
            <input
              type="file"
              accept=".pdf,.docx,.doc,.txt,.md"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-sm text-zinc-600 dark:text-zinc-400"
            />
          </label>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <label className={label}>
            Job title
            <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} className={input} placeholder="Backend Engineer" />
          </label>
          <label className={label}>
            Location
            <input value={jobLocation} onChange={(e) => setJobLocation(e.target.value)} className={input} placeholder="London" />
          </label>
        </div>
        <label className={label}>
          Job description
          <textarea
            rows={5}
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the posting — keywords are matched against the real text, never invented."
            className={input}
          />
        </label>
        <button type="submit" disabled={busy} className={button}>
          {busy ? "Scoring…" : "Score my resume"}
        </button>
      </form>

      {error ? (
        <p role="status" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      ) : null}

      {report ? (
        <div className="mt-6 flex flex-col gap-4">
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-semibold text-black dark:text-zinc-50">
              {report.overall_score}
            </span>
            <span className="text-sm text-zinc-500">/ 100 overall ATS score</span>
          </div>
          <ul className="flex flex-col gap-2">
            {Object.entries(report.category_scores).map(([name, cat]) => (
              <li key={name} className="text-sm">
                <div className="flex justify-between text-zinc-700 dark:text-zinc-300">
                  <span className="capitalize">{name.replace(/_/g, " ")}</span>
                  <span className="font-mono">
                    {cat.score}/{cat.max_score}
                  </span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-black/10 dark:bg-white/10">
                  <div
                    className="h-1.5 rounded-full bg-black dark:bg-white"
                    style={{
                      width: `${Math.round((cat.score / Math.max(cat.max_score, 1)) * 100)}%`,
                    }}
                  />
                </div>
                {cat.suggestions?.length ? (
                  <p className="mt-1 text-xs text-zinc-500">{cat.suggestions[0]}</p>
                ) : null}
              </li>
            ))}
          </ul>
          {report.missing_keywords.length ? (
            <div>
              <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Missing keywords
              </h3>
              <p className="mt-1 text-sm text-zinc-500">
                {report.missing_keywords.join(", ")} — only add these if you actually have them.
              </p>
            </div>
          ) : (
            <p className="text-sm text-zinc-500">No missing keywords against this posting.</p>
          )}
        </div>
      ) : null}
    </section>
  );
}

