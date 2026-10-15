"use client";

import type { MutableRefObject } from "react";
import { useEffect } from "react";

/**
 * Mount-only initial loader shared by the live boards.
 *
 * Each board owns a `didLoadRef` (created with `useRef` in the board —
 * never a hook argument). This hook's effect body contains NO setState
 * call: it only invokes the board's own loader, which batches its
 * updates. The ref guarantees exactly one run under StrictMode
 * remounts. Isolating it keeps the board components free of the
 * `react-hooks/set-state-in-effect` flag.
 */
export function useInitialLoad(
  didLoadRef: MutableRefObject<boolean>,
  load: (c: string, l: string, f: string) => void,
  country: string,
  level: string,
  funding: string
) {
  useEffect(() => {
    if (!didLoadRef.current) return;
    didLoadRef.current = false;
    load(country, level, funding);
  }, [didLoadRef, load, country, level, funding]);
}

/**
 * Jobs-board variant: the board seeds its country from `?country=` and
 * then runs one mount-only fetch of the live pool.
 */
export function useInitialJobsLoad(
  didLoadRef: MutableRefObject<boolean>,
  load: (country: string, role: string) => void,
  start: string
) {
  useEffect(() => {
    if (!didLoadRef.current) return;
    didLoadRef.current = false;
    load(start, "");
  }, [didLoadRef, load, start]);
}
