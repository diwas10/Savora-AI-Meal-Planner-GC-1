"use client";

import { useEffect } from "react";

/** Registers `/sw.js` (production builds only, so development never serves stale code). */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
      // Registration failure only disables offline support; the app still works.
    });
  }, []);
  return null;
}
