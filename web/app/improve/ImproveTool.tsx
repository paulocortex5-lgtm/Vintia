"use client";

/**
 * Session-gated CV improver: the real tool loads client-side only and
 * only after the session check, so signed-out visitors never receive
 * the tool bundle or markup — the public page keeps its marketing copy.
 */

import dynamic from "next/dynamic";

import RequireSession from "../../components/RequireSession";

const CvImprover = dynamic(() => import("./CvImprover"), { ssr: false });

export default function ImproveTool() {
  return (
    <RequireSession tool="The CV improver">
      <CvImprover />
    </RequireSession>
  );
}
