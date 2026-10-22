"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { BrandMark } from "@/components/functional/Brand";
import { useProfileQuery } from "@/core/private/UserProfile/service/profile.query";
import { useCurrentUserQuery } from "@/core/public/Auth/service/auth.query";
import { useIsClient } from "@/hooks/useIsClient";
import { ApiError, getStoredToken, setStoredToken } from "@/lib/api-request";

/**
 * Client route protection for `(protected)`: no token -> /login; an invalid token is
 * cleared; no profile (404) or too few seed dishes -> /onboarding.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isClient = useIsClient();
  const token = isClient ? getStoredToken() : null;
  const userQuery = useCurrentUserQuery(Boolean(token));
  const profileQuery = useProfileQuery(Boolean(token));
  const onOnboarding = pathname.startsWith("/onboarding");

  // "No profile yet" is data (null), not an error, so the query never flips back to
  // pending when another screen subscribes to it.
  const needsOnboarding = profileQuery.data === null || profileQuery.data?.needsSeedPicks === true;

  useEffect(() => {
    if (!isClient) return;
    if (!token) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    if (userQuery.error instanceof ApiError && userQuery.error.status === 401) {
      setStoredToken(null);
      router.replace("/login");
      return;
    }
    if (needsOnboarding && !onOnboarding) router.replace("/onboarding");
  }, [isClient, token, userQuery.error, needsOnboarding, onOnboarding, pathname, router]);

  const ready =
    isClient &&
    token &&
    userQuery.data &&
    (profileQuery.data !== undefined || profileQuery.isError) &&
    (onOnboarding || !needsOnboarding);

  if (!ready) return <SplashScreen />;
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
