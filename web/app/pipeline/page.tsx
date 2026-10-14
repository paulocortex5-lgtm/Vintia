import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "The Vantia Pipeline — jobs and scholarships, step by step",
  description:
    "Two live application pipelines: search screened visa-sponsored jobs or funded " +
    "scholarships, tailor your CV, track applications and alerts — every step links the " +
    "page that actually performs it. No step is aspirational.",
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
      name: "Jobs Pipeline",
      item: {
        "@type": "HowTo",
        name: "Vantia jobs pipeline",
        description: "From search to application — every step verified.",
      },
    },
    {
      "@type": "ListItem",
      position: 2,
      name: "Scholarships Pipeline",
      item: {
        "@type": "HowTo",
        name: "Vantia scholarships pipeline",
        description: "From discovery to funding — every step verified.",
      },
    },
  ],
};

type Tier = "Free" | "Pro" | "Business";
type Status = "live" | "locked";

type Step = {
  title: string;
  note: string;
  href: string;
  tier: Tier;
  cost: string;
  status: Status;
};

const COUNTRIES = ["UK", "DE", "IE", "SE", "CA", "AU", "NZ", "JP", "All"];

// ── Jobs Pipeline (Part 4.1) — 10 steps, all live or tier-gated ──────────
const JOB_STEPS: Step[] = [
  { title: "Search visa-sponsored jobs", note: "Filter by country, role, sector and visa route — every link verified direct to the employer.", href: "/jobs", tier: "Free", cost: "Free", status: "live" },
  { title: "Get recommendations from your CV", note: "Upload your CV → top 20 jobs ranked by match score.", href: "/jobs/recommended", tier: "Free", cost: "Free", status: "live" },
  { title: "Upload your CV", note: "PDF/DOCX → your private workspace.", href: "/improve", tier: "Free", cost: "Free", status: "live" },
  { title: "Scan CV against job", note: "12-category ATS report, scored 0–100.", href: "/ats", tier: "Free", cost: "2,000 credits", status: "live" },
  { title: "Map CV to job spec", note: "Field-by-field gap analysis with concrete bridge suggestions.", href: "/ats", tier: "Pro", cost: "6,000 credits", status: "locked" },
  { title: "Improve your CV", note: "AI rewriting targeted to this job — fact-preserving, reviewable.", href: "/improve", tier: "Free", cost: "8,000 credits", status: "live" },
  { title: "Refine with chat", note: "Conversational refinement — Free 3 / Pro 20 / Business unlimited turns.", href: "/improve", tier: "Free", cost: "2,000 credits/turn", status: "live" },
  { title: "Generate cover letter", note: "250–400 words tailored to the job, from your own facts.", href: "/cover-letter", tier: "Free", cost: "5,000 credits", status: "live" },
  { title: "Mock interview prep", note: "10 likely questions with model answers grounded in your CV.", href: "/ats", tier: "Pro", cost: "4,000 credits", status: "locked" },
  { title: "Download and apply", note: "PDF export + verified direct employer link — never a recruiter.", href: "/applications", tier: "Free", cost: "Free", status: "live" },
];

// ── Scholarships Pipeline (Part 4.2) — 7 steps, all live ─────────────────
const SCHOLARSHIP_STEPS: Step[] = [
  { title: "Find funded scholarships", note: "Filter by country, degree level, field and deadline.", href: "/scholarships", tier: "Free", cost: "Free", status: "live" },
  { title: "Check credential equivalence", note: "Anabin / ENIC-UK / WES / VETASSESS / NZQA crosswalks.", href: "/scholarships", tier: "Free", cost: "Free", status: "live" },
  { title: "Match your profile", note: "Fit score against the scholarship criteria.", href: "/scholarships", tier: "Free", cost: "2,000 credits", status: "live" },
  { title: "Generate Statement of Purpose", note: "490–510 words mapped to the rubric.", href: "/improve", tier: "Free", cost: "6,000 credits", status: "live" },
  { title: "Generate research proposal", note: "MRes/PhD skeleton with a literature gap.", href: "/improve", tier: "Free", cost: "12,000 credits", status: "live" },
  { title: "Track deadlines", note: "Calendar export and reminder alerts.", href: "/alerts", tier: "Free", cost: "Free", status: "live" },
  { title: "Download and apply", note: "PDF export + direct scholarship portal link.", href: "/scholarships", tier: "Free", cost: "Free", status: "live" },
];

const TIER_STYLE: Record<Tier, string> = {
  Free: "bg-black/5 text-zinc-600 dark:bg-white/10 dark:text-zinc-300",
  Pro: "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300",
  Business: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300",
};

function CountryTabs() {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {COUNTRIES.map((c) => (
        <Link
          key={c}
          href={c === "All" ? "/jobs" : `/jobs?country=${c}`}
          className="rounded-full border border-black/10 px-3 py-1 text-xs font-medium text-zinc-600 hover:border-black/40 dark:border-white/15 dark:text-zinc-300 dark:hover:border-white/40"
        >
          {c}
        </Link>
      ))}
    </div>
  );
}

function Track({
  id,
  title,
  description,
  steps,
  showCountries,
}: {
  id: string;
  title: string;
  description: string;
  steps: Step[];
  showCountries: boolean;
}) {
  return (
    <section id={id} className="mt-12 scroll-mt-8">
      <h2 className="text-xl font-semibold tracking-tight text-black dark:text-zinc-50">{title}</h2>
      <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-600 dark:text-zinc-400">{description}</p>
      {showCountries ? <CountryTabs /> : null}
      <ol className="mt-6 flex flex-col gap-3">
        {steps.map((step, index) => (
          <li key={`${step.title}-${index}`}>
            <Link
              href={step.href}
              className="block rounded-2xl border border-black/10 bg-white p-5 transition hover:border-black/30 dark:border-white/10 dark:bg-zinc-950 dark:hover:border-white/30"
            >
              <span className="flex items-center justify-between gap-3">
                <span className="font-mono text-xs text-zinc-500">step {index + 1}</span>
                <span className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${TIER_STYLE[step.tier]}`}
                  >
                    {step.tier}
                  </span>
                  <span className="text-[11px] text-zinc-500">{step.cost}</span>
                  <span
                    className={
                      step.status === "live"
                        ? "inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                        : "inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                    }
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        step.status === "live" ? "bg-emerald-500" : "bg-amber-500"
                      }`}
                    />
                    {step.status === "live" ? "live" : "Pro — upgrade"}
                  </span>
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
          Two pipelines: jobs and scholarships
        </h1>
        <p className="mt-4 leading-7 text-zinc-600 dark:text-zinc-400">
          Vantia is two honest pipelines, not a pile of disconnected tools. Every
          step below links the page that actually performs it. A step is either
          live or tier-gated to Pro — nothing is a placeholder, and every step is
          shipping today.
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
            Jobs Pipeline
          </a>
          <a
            href="#scholarships"
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
          >
            Scholarships Pipeline
          </a>
        </div>

        <Track
          id="jobs"
          title="Jobs Pipeline"
          description="From search to application — every step verified against the employer's own portal."
          steps={JOB_STEPS}
          showCountries
        />
        <Track
          id="scholarships"
          title="Scholarships Pipeline"
          description="From discovery to funding — every programme sourced from its official page."
          steps={SCHOLARSHIP_STEPS}
          showCountries={false}
        />

        <p className="mt-10 text-xs text-zinc-500">
          Every live step opens the same tool the pipeline itself uses, metered
          against your account at published prices — see your balance, packs and
          invoices on the{" "}
          <Link
            href="/credits/dashboard"
            className="font-medium text-zinc-700 underline dark:text-zinc-300"
          >
            credits dashboard
          </Link>
          . Pro steps (CV-to-job mapping, mock interview) show an upgrade prompt
          instead of running on the free tier.
        </p>
      </main>
    </div>
  );
}
