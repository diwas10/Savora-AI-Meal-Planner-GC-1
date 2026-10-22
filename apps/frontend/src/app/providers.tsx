"use client";

import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { MotionConfig } from "motion/react";
import { useState, type ReactNode } from "react";
import { ApiError, QUERY_CACHE_KEY } from "@/lib/api-request";

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: WEEK_MS, // must outlive the persisted copy
        refetchOnWindowFocus: true,
        // Client errors (401, 404, 409, 422) are answers, not glitches: never retry them.
        retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
      },
    },
  });
}

/**
 * Successful reads (profile, plans, targets) are persisted to this device so saved plans
 * stay readable offline in the installed app. Polls are not persisted; logout clears it.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(makeClient);
  const [persister] = useState(() =>
    typeof window === "undefined"
      ? null
      : createSyncStoragePersister({ storage: window.localStorage, key: QUERY_CACHE_KEY }),
  );
  const content = <MotionConfig reducedMotion="user">{children}</MotionConfig>;
  if (!persister) return <QueryClientProvider client={queryClient}>{content}</QueryClientProvider>;
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: WEEK_MS,
        buster: "savora-v1",
        dehydrateOptions: {
          shouldDehydrateQuery: (q) => q.state.status === "success" && q.queryKey[0] !== "substitutions",
        },
      }}
    >
      {content}
    </PersistQueryClientProvider>
  );
}
