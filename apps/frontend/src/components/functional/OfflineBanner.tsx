"use client";

import { WifiOff } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useOnline } from "@/hooks/useOnline";

/** Saved views keep working offline; generation and AI need a connection. */
export function OfflineBanner() {
  const online = useOnline();
  return (
    <AnimatePresence>
      {!online && (
        <motion.div
          role="status"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="overflow-hidden bg-warning-soft text-warning-foreground"
        >
          <p className="flex items-center justify-center gap-2 px-4 py-2 pt-safe text-sm font-medium">
            <WifiOff className="size-4" aria-hidden />
            You&apos;re offline. Saved plans stay readable; planning and Discover need a connection.
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
