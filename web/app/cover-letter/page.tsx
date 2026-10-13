import type { Metadata } from "next";
import Link from "next/link";

import CoverLetterGenerator from "./CoverLetterGenerator";

export const metadata: Metadata = {
  title: "Cover Letter Generator built from your CV and the posting",
  description:
    "Vantia drafts cover letters from verbatim achievements in your resume " +
    "and the real job posting — no fake availability, no invented contact " +
    "details, keywords spelled the way your CV spells them.",
  keywords: ["cover letter generator", "cover letter for job", "tailored cover letter"],
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Vantia Cover Letter Generator",
  serviceType: "Cover letter generation",
  provider: { "@type": "Organization", name: "Vantia" },
  description:
    "Facts-only cover letters: verbatim quantified achievements, posting-matched keywords, no invented details.",
};

export default function CoverLetterPage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-2xl">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Cover letters that couldn&apos;t be sent about anyone else
        </h1>
        <p className="mt-4 leading-7 text-zinc-600 dark:text-zinc-400">
          A cover letter should only say things you can evidence. Vantia builds
          yours from verbatim, quantified achievements in your own resume and
          the requirements in the actual posting.
        </p>
        <ul className="mt-6 flex flex-col gap-3 text-sm leading-6 text-zinc-700 dark:text-zinc-300">
          <li>• Up to two verbatim quantified achievements — or the section is dropped</li>
          <li>• Keywords spelled the way your CV spells them</li>
          <li>• No fake availability, no fabricated contact details, no placeholders</li>
          <li>• Loaded through the same robots/rate-limit respecting fetchers as the job trail</li>
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
            href="/improve"
          >
            Improve the CV first
          </Link>
        </div>
        <CoverLetterGenerator />
        <p className="mt-8 text-xs text-zinc-500">
          Letters are written deterministically from your facts and the posting
          you provide — stamped &quot;manual&quot; because you pasted it. Sign in
          for posting-URL loading at launch.
        </p>
      </main>
    </div>
  );
}
