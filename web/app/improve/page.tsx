import type { Metadata } from "next";
import Link from "next/link";

import CvImprover from "./CvImprover";

export const metadata: Metadata = {
  title: "CV Improvement — targeted rewrites that keep your facts",
  description:
    "Vantia's CV improver restructures your resume for ATS and role fit using " +
    "only facts already in it — reviewable edits, ranked by impact, never " +
    "fabricated experience.",
  keywords: ["CV improvement", "resume rewriter", "ATS CV", "CV optimization"],
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Vantia CV Improvement",
  serviceType: "CV improvement",
  provider: { "@type": "Organization", name: "Vantia" },
  description:
    "Fact-preserving CV improvements: canonical structure, keyword mirroring only for skills you evidenced, ranked reviewable edits.",
};

export default function ImprovePage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-2xl">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          CV improvement, minus the fiction
        </h1>
        <p className="mt-4 leading-7 text-zinc-600 dark:text-zinc-400">
          AI résumé tools are good at inventing experience you never had. Ours
          isn&apos;t allowed to: every edit preserves your facts, and anything
          the tool can&apos;t do honestly shows up as an explicit gap instead
          of plausible-sounding text.
        </p>
        <ul className="mt-6 flex flex-col gap-3 text-sm leading-6 text-zinc-700 dark:text-zinc-300">
          <li>• Canonical ATS structure rebuilt from your existing content</li>
          <li>• Keyword mirroring only for skills already evidenced in your CV</li>
          <li>• Up to 30 ranked, reviewable edits — you approve what ships</li>
          <li>• Optional AI polish, schema-validated, never changing your identity fields</li>
        </ul>
        <div className="mt-8 flex flex-wrap gap-4">
          <Link
            className="rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-white dark:text-black dark:hover:bg-zinc-300"
            href="/waitlist"
          >
            Join the waitlist
          </Link>
          <Link
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
            href="/ats"
          >
            See the ATS checker
          </Link>
        </div>
        <CvImprover />
        <p className="mt-8 text-xs text-zinc-500">
          Edits run deterministically through the same improver the pipeline
          uses — your identity fields are re-stamped from your text and never
          model-owned. Join the waitlist for saved workspaces at launch.
        </p>
      </main>
    </div>
  );
}
