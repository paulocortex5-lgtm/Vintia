import type { Metadata } from "next";
import Link from "next/link";

import AtsScanner from "./AtsScanner";

export const metadata: Metadata = {
  title: "ATS Resume Score Checker",
  description:
    "Score your CV against the twelve-point ATS rubric Vantia uses — keyword " +
    "coverage, structure, dated experience and per-category fix suggestions, " +
    "run locally against your own resume.",
  keywords: ["ATS checker", "resume score", "ATS scan", "CV score"],
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Vantia ATS Resume Score Checker",
  serviceType: "ATS resume scoring",
  provider: { "@type": "Organization", name: "Vantia" },
  description:
    "Twelve-point deterministic ATS scoring with keyword coverage and concrete per-category suggestions.",
};

export default function AtsPage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-2xl">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          ATS resume score checker
        </h1>
        <p className="mt-4 leading-7 text-zinc-600 dark:text-zinc-400">
          Most applications die in the applicant tracking system before a human
          reads them. Vantia scores your CV against a transparent twelve-point
          rubric — the same one it uses end-to-end when scanning your CV
          against a live job posting.
        </p>
        <ul className="mt-6 flex flex-col gap-3 text-sm leading-6 text-zinc-700 dark:text-zinc-300">
          <li>• Keyword coverage against the actual posting, with honest gap reports</li>
          <li>• Structure, dated-experience and contact checks — no invented fixes</li>
          <li>• Every sub-100 category ships a concrete suggestion</li>
          <li>• Deterministic: the same inputs always produce the same score</li>
        </ul>
        <div className="mt-8 flex flex-wrap gap-4">
          <Link
            className="rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-white dark:text-black dark:hover:bg-zinc-300"
            href="/dashboard"
          >
            Sign in
          </Link>
          <Link
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
            href="/status"
          >
            Build status
          </Link>
        </div>
        <AtsScanner />
        <p className="mt-8 text-xs text-zinc-500">
          Scoring is deterministic and runs against the engine&apos;s twelve-point
          rubric — the same code path the full pipeline uses. Sign in for
          workspace uploads and metered runs at launch.
        </p>
      </main>
    </div>
  );
}
