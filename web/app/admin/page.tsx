import type { Metadata } from "next";

import AdminConsole from "./AdminConsole";
import AdminGate from "./AdminGate";

// Hidden admin panel: reachable only by typing /admin — never linked from
// the UI, noindexed, and absent from the sitemap (tests enforce all three).
// On top of that, AdminGate renders the console only for the signed-in
// account holding role=admin in Supabase (first Google sign-in, migration
// 0007); the engine token inside the console stays the second factor.
export const metadata: Metadata = {
  title: "Admin",
  description: "Vantia administration panel (not public).",
  robots: { index: false, follow: false },
};

export default function AdminPage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-3xl">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Admin
        </h1>
        <AdminGate>
          <AdminConsole />
        </AdminGate>
      </main>
    </div>
  );
}
