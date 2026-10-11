import type { Metadata } from "next";

import Dashboard from "./Dashboard";

// Task 13.1: the workspace surface is a utility route — noindex, never in
// the sitemap (the SEO tests enforce exactly that boundary).
export const metadata: Metadata = {
  title: "Workspace Dashboard",
  description:
    "Your Vantia workspace: engine status, credit balance, and one-click " +
    "access to the ATS scanner, CV improver and cover letter generator.",
  robots: { index: false, follow: false },
};

export default function DashboardPage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-3xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Workspace
        </h1>
        <Dashboard />
      </main>
    </div>
  );
}