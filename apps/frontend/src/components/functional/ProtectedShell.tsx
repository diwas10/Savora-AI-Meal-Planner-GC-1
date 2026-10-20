"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { useProfileQuery } from "@/core/private/UserProfile/service/profile.query";
import { useCurrentUserQuery } from "@/core/public/Auth/service/auth.query";
import { ApiError, getStoredToken, setStoredToken } from "@/lib/api-request";

function subscribeNoop() {
  return () => {};
}

export function ProtectedShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isClient = useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false,
  );

  const token = isClient ? getStoredToken() : null;
  const userQuery = useCurrentUserQuery(isClient && Boolean(token));
  const profileQuery = useProfileQuery(isClient && Boolean(token));

  useEffect(() => {
    if (!isClient) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    if (userQuery.isError) {
      setStoredToken(null);
      router.replace("/login");
      return;
    }
    if (profileQuery.isError) {
      const err = profileQuery.error;
      if (err instanceof ApiError && err.status === 404 && pathname !== "/onboarding") {
        router.replace("/onboarding");
      }
      return;
    }
    if (
      profileQuery.data?.needsSeedPicks &&
      pathname !== "/onboarding" &&
      pathname !== "/profile"
    ) {
      router.replace("/onboarding");
    }
  }, [
    isClient,
    token,
    userQuery.isError,
    profileQuery.isError,
    profileQuery.error,
    profileQuery.data,
    pathname,
    router,
  ]);

  const handleLogout = () => {
    setStoredToken(null);
    router.replace("/login");
  };

  if (!isClient || !token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50 p-8 text-sm text-neutral-600">
        Checking authentication...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-3.5">
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="text-lg font-extrabold text-emerald-800">
              Savora
            </Link>
            <nav className="flex items-center gap-4 text-sm font-medium">
              <Link
                href="/dashboard"
                className={
                  pathname === "/dashboard"
                    ? "text-emerald-700 underline underline-offset-4"
                    : "text-neutral-700 hover:text-emerald-700"
                }
              >
                Weekly Plan
              </Link>
              <Link
                href="/craving"
                className={
                  pathname === "/craving"
                    ? "text-emerald-700 underline underline-offset-4"
                    : "text-neutral-700 hover:text-emerald-700"
                }
              >
                Craving Assistant
              </Link>
              <Link
                href="/profile"
                className={
                  pathname === "/profile"
                    ? "text-emerald-700 underline underline-offset-4"
                    : "text-neutral-700 hover:text-emerald-700"
                }
              >
                Profile & Targets
              </Link>
              <Link
                href="/onboarding"
                className={
                  pathname === "/onboarding"
                    ? "text-emerald-700 underline underline-offset-4"
                    : "text-neutral-700 hover:text-emerald-700"
                }
              >
                Onboarding
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-3 text-xs text-neutral-600">
            {userQuery.data && <span>{userQuery.data.displayName}</span>}
            <button
              type="button"
              onClick={handleLogout}
              className="rounded border border-neutral-300 px-2.5 py-1 font-medium text-neutral-700 hover:bg-neutral-100"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}
