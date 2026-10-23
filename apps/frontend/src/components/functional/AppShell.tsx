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

      {/* Desktop: the same four destinations as a sidebar. */}
      <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col border-r border-border/70 bg-surface/60 px-4 py-6 lg:flex">
        <div className="flex items-center justify-between px-3">
          <Link href="/dashboard" aria-label="Savora home">
            <Wordmark />
          </Link>
          <ThemeToggle />
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
                          className="absolute inset-0 rounded-2xl bg-primary-soft"
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
      </aside>

      <div className="min-w-0 flex-1">
        <OfflineBanner />
        <main id="main" className="mx-auto w-full max-w-3xl px-4 pb-32 pt-safe sm:px-6 lg:max-w-4xl lg:pb-12">
          {children}
        </main>
      </div>

      {/* Mobile and tablet: floating glass tab bar above the home indicator. */}
      <nav aria-label="Primary" className="fixed inset-x-0 bottom-safe z-40 flex justify-center px-4 lg:hidden">
        <LayoutGroup id="tabbar">
          <ul className="glass flex w-full max-w-md items-center justify-between rounded-pill p-1.5">
            {TABS.map(({ href, label, Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href} className="flex-1">
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex h-14 flex-col items-center justify-center gap-0.5 rounded-pill text-[11px] font-semibold transition-colors",
                      active ? "text-primary-soft-foreground" : "text-muted-foreground",
                    )}
                  >
                    {active && (
                      <motion.span
                        layoutId="tab-active"
                        className="absolute inset-0 rounded-pill bg-primary-soft"
                        transition={spring}
                      />
                    )}
                    <Icon className="relative size-[22px]" strokeWidth={active ? 2.3 : 1.9} aria-hidden />
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
