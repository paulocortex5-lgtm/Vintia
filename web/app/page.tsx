import Image from "next/image";
import Link from "next/link";

const tools = [
  { href: "/ats", title: "ATS resume scoring", note: "Twelve-point rubric against the real posting — free, deterministic." },
  { href: "/improve", title: "CV improvement", note: "Ranked, reviewable edits that only touch facts you already have." },
  { href: "/cover-letter", title: "Cover letters", note: "Written from your resume and the posting — never invented details." },
  { href: "/jobs", title: "Visa-sponsored jobs", note: "Every European country, sponsorship as a tag, never a filter." },
  { href: "/scholarships", title: "Funded scholarships", note: "Fully funded matches with Statement of Purpose generation." },
  { href: "/credits", title: "Credits, not subscriptions", note: "One-time packs, published prices, free monthly allowance." },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="w-full max-w-3xl px-6 py-20 sm:px-10">
        <p className="text-sm font-medium text-zinc-500">Vantia — universal opportunity engine</p>
        <h1 className="mt-3 max-w-2xl text-4xl font-semibold leading-tight tracking-tight text-black dark:text-zinc-50">
          Every application, targeted and verified — free of middlemen.
        </h1>
        <p className="mt-5 max-w-xl leading-7 text-zinc-600 dark:text-zinc-400">
          Vantia replaces predatory job boards and recruitment agencies with a
          direct pipeline: visa-sponsorship filtering across Europe, funded
          scholarship matching, ATS-honest resume scoring, fact-preserving CV
          improvement and cover letters built from your own experience.
        </p>

        <div className="mt-8 flex flex-wrap gap-4">
          <Link
            className="rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-white dark:text-black dark:hover:bg-zinc-300"
            href="/dashboard"
          >
            Open the workspace
          </Link>
          <Link
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
            href="/dashboard"
          >
            Sign in
          </Link>
        </div>

        <ul className="mt-12 grid gap-4 sm:grid-cols-2">
          {tools.map((tool) => (
            <li key={tool.href}>
              <Link
                href={tool.href}
                className="block rounded-2xl border border-black/10 bg-white p-5 transition hover:border-black/30 dark:border-white/10 dark:bg-zinc-950 dark:hover:border-white/30"
              >
                <span className="text-sm font-semibold text-black dark:text-zinc-100">{tool.title}</span>
                <span className="mt-1 block text-xs leading-5 text-zinc-500">{tool.note}</span>
              </Link>
            </li>
          ))}
        </ul>

        <div className="mt-12 flex items-center gap-4">
          <Image
            className="dark:invert h-5 w-[100px]"
            src="/next.svg"
            alt="Built with Next.js"
            width={100}
            height={20}
            priority
          />
          <Link
            href="/status"
            className="text-sm text-zinc-500 underline hover:text-black dark:hover:text-zinc-100"
          >
            Live build status
          </Link>
        </div>
      </main>
    </div>
  );
}
