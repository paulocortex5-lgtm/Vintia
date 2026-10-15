"use client";

/**
 * Shared signed-in state for the marketing surface.
 *
 * Every marketing page keeps its server-rendered SEO copy, but its call
 * to action reflects the real session: a signed-in visitor is offered
 * the workspace, never a second "Sign in". The check is the same
 * localStorage session the tools gate on — never invented, read lazily
 * on first render and refreshed on cross-tab storage events.
 */

import { useState } from "react";

import { loadSession, signOut, type Session } from "../lib/engine";
import { useSubscribeStorage } from "./useSubscribeStorage";
export type UseSession = {
  loading: boolean;
  session: Session | null;
  signedIn: boolean;
  email: string;
  refresh: () => void;
};

export function useSession(): UseSession {
  // Lazy initial state — the session is read during the first render,
  // never set synchronously inside an effect. Cross-tab updates arrive
  // through the storage event subscription below.
  const [session, setSession] = useState<Session | null>(() => loadSession());

  function refresh() {
    setSession(loadSession());
  }

  useSubscribeStorage(refresh);

  return {
    loading: false,
    session,
    signedIn: session !== null,
    email: session?.user?.email ?? "",
    refresh,
  };
}

export { signOut };
