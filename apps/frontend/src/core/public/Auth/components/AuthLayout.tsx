"use client";

import { Coffee, Leaf, Salad, Soup, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import type { ReactNode } from "react";
import { Wordmark } from "@/components/functional/Brand";
import { ThemeToggle } from "@/core/common/theme/ThemeToggle";

const FLOATERS = [
  { Icon: Salad, className: "left-[8%] top-[18%] size-14", delay: 0 },
  { Icon: Soup, className: "right-[10%] top-[30%] size-16", delay: 0.6 },
  { Icon: Coffee, className: "left-[18%] bottom-[22%] size-12", delay: 1.2 },
  { Icon: Leaf, className: "right-[22%] bottom-[14%] size-10", delay: 1.8 },
];

/** Brand panel + form; on phones the panel becomes a short header. */
export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-background lg:grid lg:grid-cols-2">
      {/* Brand panel: on mobile, a compact top header; on desktop, a full-height editorial panel */}
      <div
        className="relative isolate overflow-hidden bg-gradient-to-br from-hero-from via-hero-via to-hero-to px-6 py-4 text-hero-ink lg:flex lg:flex-col lg:justify-between lg:p-12 lg:min-h-dvh"
        style={{
          backgroundImage: "linear-gradient(135deg, var(--hero-from), var(--hero-via), var(--hero-to))",
        }}
      >
        {FLOATERS.map(({ Icon, className, delay }) => (
          <motion.span
            key={className}
            className={`absolute hidden opacity-20 lg:block ${className}`}
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 6, repeat: Infinity, delay, ease: "easeInOut" }}
            aria-hidden
          >
            <Icon className="size-full" strokeWidth={1.4} />
          </motion.span>
        ))}
        <div className="flex items-center justify-between">
          <Wordmark className="[&_span]:text-hero-ink" />
          <ThemeToggle onHero />
        </div>
        <div className="relative mt-8 hidden max-w-md lg:block lg:mt-0">
          <p className="mb-3 inline-flex items-center gap-1.5 rounded-pill bg-hero-ink/15 px-3 py-1 text-xs font-semibold">
            <Sparkles className="size-3.5" aria-hidden /> Explainable meal planning
          </p>
          <h2 className="text-3xl font-bold leading-tight tracking-tight lg:text-5xl">
            Seven days of meals that fit you, and say why.
          </h2>
          <p className="mt-3 text-lg opacity-90">
            Your cuisines, your rules, your allergies. Every plan is checked as a whole week and
            every swap keeps the rest of it.
          </p>
        </div>
        <p className="relative hidden text-sm opacity-75 lg:block">Savora GC1</p>
      </div>

      {/* Main form: cleanly centered on all screen sizes */}
      <main className="flex flex-1 flex-col items-center justify-center px-4 py-8 lg:px-12 lg:py-12">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md rounded-sheet bg-surface p-6 shadow-float ring-1 ring-border/70 sm:p-8"
        >
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          <p className="mb-6 mt-1 text-[15px] text-muted-foreground">{subtitle}</p>
          {children}
        </motion.div>
      </main>
    </div>
  );
}
