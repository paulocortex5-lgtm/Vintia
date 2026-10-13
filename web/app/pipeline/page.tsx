import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "The Vantia Pipeline — jobs and scholarships, step by step",
  description:
    "Two honest application pipelines: sign in, discover screened visa-sponsored " +
    "jobs or funded scholarships, tailor your CV, draft the letter, track every " +
    "credit — each step links the page that actually performs it.",
  keywords: ["job application pipeline", "scholarship application steps", "job search workflow"],
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "ItemList",
  name: "Vantia application pipelines",
  itemListElement: [
    {
      "@type": "ListItem",
      position: 1,
      name: "Job pipeline",
      item: {
        "@type": "HowTo",
        name: "Vantia job pipeline",
        description: "From account to submitted application for job seekers.",
        step: [
          { "@type": "HowToStep", name: "Create your account", text: "Google or email sign-in; the free monthly allowance starts here." },
          { "@type": "HowToStep", name: "Score your baseline CV", text: "Twelve-point ATS rubric before you tailor anything." },
          { "@type": "HowToStep", name: "Pick a screened, visa-sponsored posting", text: "Fraud scores, sponsor-register badges, dead-link refusal." },
          { "@type": "HowToStep", name: "Score against that posting", text: "Keyword coverage and honest gap reports against the real requirements." },
          { "@type": "HowToStep", name: "Apply the ranked edits", text: "Fact-preserving, reviewable — you approve every change." },
          { "@type": "HowToStep", name: "Draft the cover letter", text: "From verbatim achievements in your CV and the posting's own keywords." },
          { "@type": "HowToStep", name: "Track every credit", text: "Balance, allowance, packs and the monthly statement." },
        ],
      },
    },
    {
      "@type": "ListItem",
      position: 2,
      name: "Scholarship pipeline",
      item: {
        "@type": "HowTo",
        name: "Vantia scholarship pipeline",
        description: "From account to submitted application for scholarship seekers.",
        step: [
          { "@type": "HowToStep", name: "Create your account", text: "Google or email sign-in; the free monthly allowance starts here." },
          { "@type": "HowToStep", name: "Browse funded programmes", text: "Official URLs, checked deadlines, honest unknowns." },
          { "@type": "HowToStep", name: "Check credential equivalence", text: "ENIC-NARIC advice on real gaps before you apply." },
          { "@type": "HowToStep", name: "Tailor your academic CV", text: "Score it against the programme's stated requirements." },
          { "@type": "HowToStep", name: "Apply ranked edits", text: "Fact-preserving improvements, every change reviewable." },
          { "@type": "HowToStep", name: "Draft the motivation letter", text: "Your achievements, the programme's wording — nothing invented." },
          { "@type": "HowToStep", name: "Track every credit", text: "Balance, allowance, packs and the monthly statement." },
        ],
      },
    },
  ],
};

type Step = { title: string; note: string; href: string; status: "live" | "soon" };

const JOB_TRACK: Step[] = [
  {
    title: "Create your account",
    note: "Google or email — the free monthly allowance (10,000 credits) starts with the account.",
    href: "/dashboard",
    status: "live",
  },
  {
    title: "Score your baseline CV",
    note: "Twelve-point rubric before you tailor anything — fix structure and dated experience first.",
    href: "/ats",
    status: "live",
  },
  {
    title: "Pick a screened, visa-sponsored posting",
    note: "Fraud scores with reports, sponsor-register badges, dead-link refusal — never a raw scrape.",
    href: "/jobs",
    status: "soon",
  },
  {
    title: "Score your CV against that posting",
    note: "Keyword coverage and honest gap reports against the posting's real requirements.",
    href: "/ats",
    status: "live",
  },
  {
    title: "Apply the ranked edits",
    note: "Up to 30 fact-preserving edits — you review and approve every change.",
    href: "/improve",
    status: "live",
  },
  {
    title: "Draft the cover letter",
    note: "From verbatim achievements in your CV and the posting's keywords — never invented details.",
    href: "/cover-letter",
    status: "live",
  },
  {
    title: "Track every credit",
    note: "Balance, allowance, packs and the monthly statement — nothing is metered silently.",
    href: "/credits/dashboard",
    status: "live",
  },
];

const SCHOLARSHIP_TRACK: Step[] = [
  {
    title: "Create your account",
    note: "Google or email — the free monthly allowance (10,000 credits) starts with the account.",
    href: "/dashboard",
    status: "live",
  },
  {
    title: "Browse funded programmes",
    note: "Chevening, Commonwealth, DAAD, Erasmus+ Mundus and more — official URLs and checked dates.",
    href: "/scholarships",
    status: "soon",
  },
  {
    title: "Check credential equivalence",
    note: "ENIC-NARIC advice on real gaps; honest unknowns when a cycle isn't published.",
    href: "/scholarships",
    status: "soon",
  },
  {
    title: "Tailor your academic CV",
    note: "Score it against the programme's stated requirements, then fix the gaps.",
    href: "/ats",
    status: "live",
  },
  {
    title: "Apply the ranked edits",
    note: "Fact-preserving improvements — identity fields are never model-owned.",
    href: "/improve",
    status: "live",
  },
  {
    title: "Draft the motivation letter",
    note: "The same facts-only generator: your achievements, the programme's wording.",
    href: "/cover-letter",
    status: "live",
  },
  {
    title: "Track every credit",
    note: "Balance, allowance, packs and the monthly statement — nothing is metered silently.",
    href: "/credits/dashboard",
    status: "live",
  },
];

function Track({
  id,
  title,
  intro,
  steps,
}: {
  id: string;
  title: string;
  intro: string;
  steps: Step[];
}) {
  return (
    <section id={id} className="mt-12 scroll-mt-8">
      <h2 className="text-xl font-semibold tracking-tight text-black dark:text-zinc-50">{title}</h2>
      <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-600 dark:text-zinc-400">{intro}</p>
      <ol className="mt-6 flex flex-col gap-3">
        {steps.map((step, index) => (
          <li key={`${step.title}-${index}`}>
            <Link
              href={step.href}
              className="block rounded-2xl border border-black/10 bg-white p-5 transition hover:border-black/30 dark:border-white/10 dark:bg-zinc-950 dark:hover:border-white/30"
            >
              <span className="flex items-center justify-between gap-3">
                <span className="font-mono text-xs text-zinc-500">step {index + 1}</span>
                <span
                  className={
                    step.status === "live"
                      ? "rounded-full bg-black/5 px-2.5 py-0.5 text-[11px] font-medium text-zinc-600 dark:bg-white/10 dark:text-zinc-300"
                      : "rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                  }
                >
                  {step.status === "live" ? "live now" : "launching soon"}
                </span>
              </span>
              <span className="mt-1 block text-sm font-semibold text-black dark:text-zinc-100">
                {step.title}
              </span>
              <span className="mt-1 block text-xs leading-5 text-zinc-500">{step.note}</span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}

export default function PipelinePage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-2xl">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          One pipeline for jobs, one for scholarships
        </h1>
        <p className="mt-4 leading-7 text-zinc-600 dark:text-zinc-400">
          Vantia is two honest pipelines, not a pile of disconnected tools.
          Each step below links the page that actually performs it — steps
          that are not live yet say so instead of pretending. Steps marked
          <em> live now</em> require a signed-in account (the free monthly
          allowance covers your first runs).
        </p>
        <div className="mt-6 flex flex-wrap gap-4">
          <Link
            className="rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-white dark:text-black dark:hover:bg-zinc-300"
            href="/dashboard"
          >
            Create your account
          </Link>
          <a
            href="#jobs"
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
          >
            Job track
          </a>
          <a
            href="#scholarships"
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
          >
            Scholarship track
          </a>
        </div>

        <Track
          id="jobs"
          title="If you are looking for a job"
          intro="Discover a screened, sponsorship-flagged posting; tailor and fix your CV against it; send a cover letter built from your own facts; watch the spend."
          steps={JOB_TRACK}
        />
        <Track
          id="scholarships"
          title="If you are looking for a scholarship"
          intro="Find a funded programme with a verified deadline; check the credential equivalence honestly; tailor your academic CV and motivation letter; watch the spend."
          steps={SCHOLARSHIP_TRACK}
        />

        <p className="mt-10 text-xs text-zinc-500">
          Nothing on this page is aspirational marketing: every live step
          opens the same tool the pipeline itself uses, metered against your
          account at published prices — and launching-soon steps link the
          page that will host them, honestly labelled.
        </p>
      </main>
    </div>
  );
}
