"use client";

import { useEffect } from "react";

/** Subscribe to cross-tab session changes; the callback fires only on
 * storage events, never synchronously inside the effect body. */
export function useSubscribeStorage(onChange: () => void) {
  useEffect(() => {
    function handle(event: StorageEvent) {
      if (event.key === "vantia_session" || event.key === null) onChange();
    }
    window.addEventListener("storage", handle);
    return () => window.removeEventListener("storage", handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
