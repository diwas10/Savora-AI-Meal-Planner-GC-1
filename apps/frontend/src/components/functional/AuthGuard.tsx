"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { BrandMark } from "@/components/functional/Brand";
import { ErrorState } from "@/components/ui/States";
import { useOnline } from "@/hooks/useOnline";
import { useProfileQuery } from "@/core/private/UserProfile/service/profile.query";
import { useCurrentUserQuery } from "@/core/public/Auth/service/auth.query";
import { useIsClient } from "@/hooks/useIsClient";
import { ApiError, hasSession, setSession } from "@/lib/api-request";

/**
 * Client route protection for `(protected)`: no session -> /login; an expired session
 * is cleared; no profile (404) or too few seed dishes -> /onboarding.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isClient = useIsClient();
  const signedIn = isClient && hasSession();
  const userQuery = useCurrentUserQuery(signedIn);
  const profileQuery = useProfileQuery(signedIn);
  const onOnboarding = pathname.startsWith("/onboarding");
  const online = useOnline();

  // "No profile yet" is data (null), not an error, so the query never flips back to
  // pending when another screen subscribes to it.
  const needsOnboarding = profileQuery.data === null || profileQuery.data?.needsSeedPicks === true;

  useEffect(() => {
    if (!isClient) return;
    if (!signedIn) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    if (userQuery.error instanceof ApiError && userQuery.error.status === 401) {
      setSession(false);
      router.replace("/login");
      return;
    }
    if (needsOnboarding && !onOnboarding) router.replace("/onboarding");
  }, [isClient, signedIn, userQuery.error, needsOnboarding, onOnboarding, pathname, router]);

  const ready =
    isClient &&
    signedIn &&
    userQuery.data &&
    (profileQuery.data !== undefined || profileQuery.isError) &&
    (onOnboarding || !needsOnboarding);

  if (!ready) {
    // Offline with nothing cached yet: say so instead of an endless splash.
    const unreachable =
      !online || (userQuery.error instanceof ApiError && userQuery.error.status === 0);
    if (isClient && signedIn && !userQuery.data && unreachable) {
      return (
        <div className="grid min-h-dvh place-items-center px-6">
          <ErrorState
            offline
            message="Open Savora once while online and your saved plans will be available offline too."
            onRetry={() => {
              void userQuery.refetch();
              void profileQuery.refetch();
            }}
          />
        </div>
      );
    }
    return <SplashScreen />;
  }
  return <>{children}</>;
}

export function SplashScreen() {
  return (
    <div className="grid min-h-dvh place-items-center bg-background" aria-busy="true" aria-live="polite">
      <div className="flex flex-col items-center gap-4">
        <BrandMark className="size-16 animate-pulse-soft" />
        <span className="sr-only">Loading Savora</span>
      </div>
    </div>
  );
}
