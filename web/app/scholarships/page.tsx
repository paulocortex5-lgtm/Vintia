import type { Metadata } from "next";
import Link from "next/link";

const ENGINE =
  process.env.NEXT_PUBLIC_ENGINE_URL || "https://vantia-engine.onrender.com";

export const metadata: Metadata = {
  title: "Funded Scholarships with Verified Deadlines",
  description:
    "Vantia tracks fully funded scholarships — Chevening, Commonwealth, " +
    "DAAD, Erasmus+ Mundus and more — with sourced deadlines, credential " +
    "equivalence checks and honest answers when a cycle isn't published.",
  keywords: ["funded scholarships", "scholarship deadlines", "Erasmus Mundus", "Chevening"],
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Vantia Scholarship Finder",
  serviceType: "Scholarship discovery",
  provider: { "@type": "Organization", name: "Vantia" },
  description:
    "Sourced scholarship database with verified official URLs, window tracking and three-valued credential equivalence.",
};

export default function ScholarshipsPage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-2xl">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Funded scholarships, sourced — not scraped guesses
        </h1>
        <p className="mt-4 leading-7 text-zinc-600 dark:text-zinc-400">
          Every scholarship in Vantia carries its official URL and the date the
          fact was checked. When a programme doesn&apos;t publish a recurring
          deadline, Vantia says <em>unknown</em> instead of inventing one.
        </p>
        <ul className="mt-6 flex flex-col gap-3 text-sm leading-6 text-zinc-700 dark:text-zinc-300">
          <li>• Chevening, Commonwealth, DAAD, Erasmus+ Mundus, Australia Awards</li>
          <li>• Credential equivalence with ENIC-NARIC advice on real gaps</li>
          <li>• Window tracking that handles year-wrapping cycles correctly</li>
          <li>• SOP + research proposal drafts built only from your facts</li>
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
            href="/pipeline#scholarships"
          >
            Follow the scholarship pipeline
          </Link>
          <Link
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
            href="/jobs"
          >
            Browse the jobs side
          </Link>
          <a
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
            href={`${ENGINE}/scholarships/calendar.ics`}
            download
          >
            Export all deadlines to calendar (.ics)
          </a>
        </div>
        <p className="mt-8 text-xs text-zinc-500">
          Part of Vantia — every programme above links its official source; the
          calendar export marks month-precision deadlines as such.
        </p>
      </main>
    </div>
  );
}
