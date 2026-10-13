import type { Metadata } from "next";
import Link from "next/link";

import RecommendedTool from "./RecommendedTool";

export const metadata: Metadata = {
  title: "Job Recommendations from Your CV — Vantia",
  description:
    "Paste your CV and get the top 20 verified, visa-sponsored jobs ranked by " +
    "deterministic match score — skills, experience, education, location, " +
    "sponsorship and recency, weighted transparently.",
  keywords: ["job recommendations", "CV job match", "visa sponsored jobs"],
};

export default function RecommendedPage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-3xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Job recommendations from your CV
        </h1>
        <p className="mt-4 leading-7 text-zinc-600 dark:text-zinc-400">
          Vantia ranks every verified job in its pool against your CV — skills
          (35%), experience (20%), education (15%), location (10%), sponsorship
          (10%) and recency (10%). Deterministic, free, and cached for 24 hours.
          Only jobs with a verified direct employer link are ever recommended.
        </p>
        <div className="mt-6 flex flex-wrap gap-4">
          <Link
            className="rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-white dark:text-black dark:hover:bg-zinc-300"
            href="/dashboard"
          >
            Sign in
          </Link>
          <Link
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
            href="/pipeline#jobs"
          >
            Follow the job pipeline
          </Link>
        </div>
        <RecommendedTool />
      </main>
    </div>
  );
}
