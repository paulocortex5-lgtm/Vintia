"use client";

/**
 * Session-aware call to action for the marketing pages.
 *
 * Signed-out visitors get the honest sign-in button; signed-in visitors
 * get "Open your workspace" plus their account email — so nobody who is
 * already signed in is ever asked to sign in again.
 */

import Link from "next/link";

import { useSession } from "../lib/useSession";

const primary =
  "rounded-full bg-black px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-white dark:text-black dark:hover:bg-zinc-300";
const secondary =
  "rounded-full border border-black/10 px-5 py-2 text-sm font-medium text-black hover:border-black/40 dark:border-white/20 dark:text-zinc-100";

export default function SessionCta({ label = "Sign in" }: { label?: string }) {
  const { loading, signedIn, email } = useSession();

  if (loading) {
    return (
      <span className={secondary} aria-hidden>
        …
      </span>
    );
  }

  if (!signedIn) {
    return (
      <Link href="/dashboard" className={primary}>
        {label}
      </Link>
    );
  }

  return (
    <span className="flex flex-wrap items-center gap-3">
      <Link href="/dashboard" className={primary}>
        Open your workspace
      </Link>
      <span className="text-xs text-zinc-500">
        Signed in{email ? ` as ${email}` : ""}
      </span>
    </span>
  );
}
