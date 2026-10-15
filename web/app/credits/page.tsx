import type { Metadata } from "next";
import Link from "next/link";

import SessionCta from "../../components/SessionCta";

export const metadata: Metadata = {
  title: "Credit Packs — pay per use, no subscription",
  description:
    "Vantia is priced in credits: 10k for $5, 50k for $20 or 250k for $80, " +
    "with a free monthly allowance every account starts on. Paid through " +
    "Paddle — Vantia never touches your card details.",
  keywords: ["credits", "pricing", "pay per use", "Paddle checkout"],
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "Offer",
  name: "Vantia credit packs",
  priceCurrency: "USD",
  price: "5.00",
  description: "One-time credit packs from $5; every account starts with a free monthly allowance.",
  seller: { "@type": "Organization", name: "Vantia" },
};

export default function CreditsPage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-2xl">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Credits, not subscriptions
        </h1>
        <p className="mt-4 leading-7 text-zinc-600 dark:text-zinc-400">
          Every account starts with a free monthly allowance. Beyond that,
          one-time credit packs — they never expire and there&apos;s no
          recurring charge to cancel.
        </p>
        <ul className="mt-6 flex flex-col gap-3 text-sm leading-6 text-zinc-700 dark:text-zinc-300">
          <li>• Free tier: 10,000 credits every month, no card required</li>
          <li>• Pack 10K — $5.00 · Pack 50K — $20.00 · Pack 250K — $80.00</li>
          <li>• A CV scan costs 2,000 credits; every price is published, nothing is metered silently</li>
          <li>• Payments run through Paddle (Merchant of Record) — card data never reaches Vantia</li>
        </ul>
        <div className="mt-8 flex flex-wrap gap-4">
          <SessionCta />
          <Link
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
            href="/credits/dashboard"
          >
            Open the credits dashboard
          </Link>
          <Link
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
            href="/credits/purchase"
          >
            View packs
          </Link>
          <Link
            className="rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100"
            href="/dashboard"
          >
            Sign in
          </Link>
        </div>
        <p className="mt-8 text-xs text-zinc-500">
          Prices are read live from the engine — nothing on this page is a
          hard-coded guess. Your balance, allowance and packs all come straight
          from the credit ledger.
        </p>
      </main>
    </div>
  );
}
