"use client";

/**
 * Session-gated recommendations tool: the real tool loads client-side only
 * and only after the session check, matching the other Vantia tools.
 */

import dynamic from "next/dynamic";

import RequireSession from "../../../components/RequireSession";

const RecommendedJobs = dynamic(() => import("./RecommendedJobs"), { ssr: false });

export default function RecommendedTool() {
  return (
    <RequireSession tool="Job recommendations">
      <RecommendedJobs />
    </RequireSession>
  );
}
