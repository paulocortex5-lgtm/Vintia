import type { Metadata } from "next";

import AuthCallback from "./AuthCallback";

// OAuth landing route: Supabase redirects back here with tokens (implicit
// hash) or a PKCE code. Utility route — noindex, never in the sitemap.
export const metadata: Metadata = {
  title: "Signing in",
  description: "Completing Supabase OAuth sign-in.",
  robots: { index: false, follow: false },
};

export default function AuthCallbackPage() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="w-full max-w-md">
        <AuthCallback />
      </main>
    </div>
  );
}