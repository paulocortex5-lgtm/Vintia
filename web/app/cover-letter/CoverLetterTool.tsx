"use client";

/**
 * Session-gated cover letter generator: the real tool loads client-side
 * only and only after the session check, so signed-out visitors never
 * receive the tool bundle or markup — the public page keeps its
 * marketing copy.
 */

import dynamic from "next/dynamic";

import RequireSession from "../../components/RequireSession";

const CoverLetterGenerator = dynamic(() => import("./CoverLetterGenerator"), {
  ssr: false,
});

export default function CoverLetterTool() {
  return (
    <RequireSession tool="The cover letter generator">
      <CoverLetterGenerator />
    </RequireSession>
  );
}
