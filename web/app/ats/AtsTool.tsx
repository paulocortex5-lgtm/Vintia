"use client";

/**
 * Session-gated ATS scanner: the real tool loads client-side only and
 * only after the session check, so signed-out visitors never receive
 * the tool bundle or markup — the public page keeps its marketing copy.
 */

import dynamic from "next/dynamic";

import RequireSession from "../../components/RequireSession";

const AtsScanner = dynamic(() => import("./AtsScanner"), { ssr: false });

export default function AtsTool() {
  return (
    <RequireSession tool="The ATS scanner">
      <AtsScanner />
    </RequireSession>
  );
}
