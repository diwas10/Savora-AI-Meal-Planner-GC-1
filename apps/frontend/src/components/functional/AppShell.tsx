"use client";

import { CalendarDays, House, Sparkles, UserRound } from "lucide-react";
import { LayoutGroup, motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Wordmark } from "@/components/functional/Brand";
import { OfflineBanner } from "@/components/functional/OfflineBanner";
import { ThemeToggle } from "@/core/common/theme/ThemeToggle";
import { spring } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** Exactly four destinations (SCREENS.md): Logout lives in Profile, not a fifth tab. */
const TABS = [
  { href: "/dashboard", label: "Home", Icon: House },
  { href: "/meal-plans", label: "My Plan", Icon: CalendarDays },
  { href: "/discover", label: "Discover", Icon: Sparkles },
  { href: "/profile", label: "Profile", Icon: UserRound },
] as const;

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-dvh bg-background lg:flex">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-pill focus:bg-surface focus:px-4 focus:py-2"
      >
        Skip to content
      </a>

      {/* Desktop: the same four destinations as a frosted glass sidebar with theme toggle at the bottom. */}
      <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col border-r border-border/70 bg-surface/75 backdrop-blur-xl px-4 py-6 lg:flex">
        <div className="flex items-center justify-between px-3">
          <Link href="/dashboard" aria-label="Savora home">
            <Wordmark />
          </Link>
        </div>
        <nav aria-label="Primary" className="mt-8 flex-1">
          <LayoutGroup id="sidebar">
            <ul className="flex flex-col gap-1">
              {TABS.map(({ href, label, Icon }) => {
                const active = isActive(pathname, href);
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "relative flex h-12 items-center gap-3 rounded-2xl px-4 text-[15px] font-medium transition-colors",
                        active ? "text-primary-soft-foreground" : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {active && (
                        <motion.span
                          layoutId="sidebar-active"
                          className="absolute inset-0 rounded-2xl bg-primary-soft shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)] ring-1 ring-primary/15"
                          transition={spring}
                        />
                      )}
                      <Icon className="relative size-5" aria-hidden />
                      <span className="relative">{label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </LayoutGroup>
        </nav>

        {/* Desktop sidebar bottom: theme switcher placed at bottom on large screens */}
        <div className="mt-auto border-t border-border/70 pt-4 px-2">
          <div className="flex items-center justify-between rounded-xl px-2 py-1 text-sm font-medium text-muted-foreground">
            <span>Appearance</span>
            <ThemeToggle />
          </div>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <OfflineBanner />
        <main id="main" className="mx-auto w-full max-w-3xl px-4 pb-32 pt-safe sm:px-6 lg:max-w-4xl lg:pb-12">
          {children}
        </main>
      </div>

      {/* Mobile and tablet: Apple Liquid Glass tab bar fixed to the bottom. */}
      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 z-50 flex justify-center px-4 pb-[max(0.75rem,env(safe-area-inset-bottom,0.75rem))] pt-2 pointer-events-none lg:hidden"
      >
        <LayoutGroup id="tabbar">
          <ul className="glass pointer-events-auto flex w-full max-w-md items-center justify-between rounded-pill p-1.5 transition-all">
            {TABS.map(({ href, label, Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href} className="flex-1">
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex h-14 flex-col items-center justify-center gap-0.5 rounded-pill text-[11px] font-semibold transition-all duration-200 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active ? "text-primary-soft-foreground" : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {active && (
                      <motion.span
                        layoutId="tab-active"
                        className="absolute inset-0 rounded-pill bg-primary-soft/90 shadow-[inset_0_1px_1px_rgba(255,255,255,0.7),0_2px_8px_-2px_rgba(31,107,84,0.2)] ring-1 ring-primary/20 dark:bg-primary-soft/60 dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] dark:ring-primary/30"
                        transition={spring}
                      />
                    )}
                    <Icon className="relative size-[22px]" strokeWidth={active ? 2.35 : 1.9} aria-hidden />
                    <span className="relative">{label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </LayoutGroup>
      </nav>
    </div>
  );
}
