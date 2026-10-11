"use client";

/**
 * Cover letter generator (task 13.4) — resume facts plus the posting you
 * paste, nothing else. The letter is stamped `manual` because the posting
 * was caller-pasted; no contact details or availability are invented.
 */

import { useState } from "react";
import { ENGINE, engineError } from "../../lib/engine";

type Result = {
  cover_letter: {
    content: string;
    sections: { heading: string; body: string }[];
    metadata: { company_name: string; job_title: string; total_word_count: number; tone: string };
    job_id: string;
  };
  provider: string;
};

const input =
  "mt-1 w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-black outline-none focus:border-black/40 dark:border-white/20 dark:bg-zinc-900 dark:text-zinc-100";
const label = "text-sm font-medium text-zinc-700 dark:text-zinc-300";
const button =
  "rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-300";

export default function CoverLetterGenerator() {
  const [resumeText, setResumeText] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [company, setCompany] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [jobLocation, setJobLocation] = useState("");
  const [tone, setTone] = useState("professional");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${ENGINE}/cover/letter`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_text: resumeText,
          job_title: jobTitle,
          company,
          job_description: jobDescription,
          job_location: jobLocation,
          tone,
        }),
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
      <form onSubmit={generate} className="flex flex-col gap-3">
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
        <div className="grid gap-3 sm:grid-cols-2">
          <label className={label}>
            Job title
            <input required value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} className={input} placeholder="Backend Engineer" />
          </label>
          <label className={label}>
            Company
            <input value={company} onChange={(e) => setCompany(e.target.value)} className={input} placeholder="Acme Robotics Ltd" />
          </label>
        </div>
        <label className={label}>
          Job description
          <textarea
            required
            rows={5}
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the posting — the letter only answers requirements it actually contains."
            className={input}
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className={label}>
            Location
            <input value={jobLocation} onChange={(e) => setJobLocation(e.target.value)} className={input} placeholder="London" />
          </label>
          <label className={label}>
            Tone
            <select value={tone} onChange={(e) => setTone(e.target.value)} className={input}>
              <option value="professional">professional</option>
              <option value="formal">formal</option>
              <option value="confident">confident</option>
              <option value="casual">casual</option>
            </select>
          </label>
        </div>
        <button type="submit" disabled={busy} className={button}>
          {busy ? "Writing…" : "Write my cover letter"}
        </button>
      </form>

      {error ? (
        <p role="status" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      ) : null}

      {result ? (
        <div className="mt-6 flex flex-col gap-3">
          <p className="text-sm text-zinc-500">
            {result.cover_letter.metadata.job_title}
            {result.cover_letter.metadata.company_name ? ` at ${result.cover_letter.metadata.company_name}` : ""} ·{" "}
            {result.cover_letter.metadata.total_word_count} words · tone: {result.cover_letter.metadata.tone} · provider: {result.provider}
          </p>
          {result.cover_letter.sections.map((section) => (
            <div key={section.heading}>
              <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">{section.heading}</h3>
              <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-zinc-700 dark:text-zinc-300">
                {section.body}
              </p>
            </div>
          ))}
          <p className="text-xs text-zinc-500">
            Written only from your resume and the posting above — nothing was invented.
          </p>
        </div>
      ) : null}
    </section>
  );
}