import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Visa-Sponsored Jobs with Register-Checked Badges",
  description:
    "Vantia surfaces visa-sponsored jobs, screens them for fraud, checks " +
    "sponsor registers per country and refuses closed listings — a job trail " +
    "you can actually trust.",
  keywords: ["visa sponsorship jobs", "sponsored jobs", "skilled worker visa jobs"],
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Vantia Sponsored Jobs Trail",
  serviceType: "Job discovery with visa sponsorship filtering",
  provider: { "@type": "Organization", name: "Vantia" },
  description:
    "Job listings with fraud screening, sponsor-register badges, closed-listing refusal and ATS-tailored resumes.",
};

export default function JobsPage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-2xl">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Visa-sponsored jobs, screened before you read them
        </h1>
        <p className="mt-4 leading-7 text-zinc-600 dark:text-zinc-400">
          Vantia doesn&apos;t just aggregate listings: every job trail runs
          through fraud screening, sponsor-register checks where a country
          publishes one, and dead-link refusal — so what you see is live and
          flagged honestly.
        </p>
        <ul className="mt-6 flex flex-col gap-3 text-sm leading-6 text-zinc-700 dark:text-zinc-300">
          <li>• Fraud scores with a report attached; scams are blocked, not downranked quietly</li>
          <li>• Sponsor-register badges — including honest &quot;pending&quot; and &quot;none known&quot; states</li>
          <li>• Closed listings are refused, robots.txt is respected, rate limits per domain</li>
          <li>• Generates an ATS-tailored resume from your verified profile</li>
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
            href="/pipeline#jobs"
          >
            Follow the job pipeline
          </Link>
          <Link
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
            href="/ats"
          >
            Score your CV first
          </Link>
        </div>
        <p className="mt-8 text-xs text-zinc-500">
          Every listing is screened for predatory postings and carries a verified
          direct employer link — never a recruiter or aggregator.
        </p>
      </main>
    </div>
  );
}
