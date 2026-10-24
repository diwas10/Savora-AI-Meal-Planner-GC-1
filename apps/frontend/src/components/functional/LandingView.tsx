"use client";

import {
  ArrowRight,
  CalendarCheck,
  Leaf,
  MessageCircle,
  Repeat2,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Wordmark } from "@/components/functional/Brand";
import { LinkButton } from "@/components/ui/Button";
import { ThemeToggle } from "@/core/common/theme/ThemeToggle";
import { useIsClient } from "@/hooks/useIsClient";
import { hasSession } from "@/lib/api-request";
import { fadeUp, stagger } from "@/lib/motion";

const FEATURES = [
  { Icon: CalendarCheck, title: "A whole week, checked", text: "21 meal slots checked together with prototype rules." },
  { Icon: Repeat2, title: "Swap without chaos", text: "Change one meal; the other 20 stay locked." },
  { Icon: MessageCircle, title: "Ask for a craving", text: "“Spicy Thai, no peanuts” in plain words." },
  { Icon: ShieldCheck, title: "Your preferences first", text: "Ingredient and diet screening; allergy safety is not verified." },
];

export function LandingView() {
  const router = useRouter();
  const isClient = useIsClient();
  const signedIn = isClient && hasSession();

  useEffect(() => {
    if (signedIn) router.replace("/dashboard");
  }, [signedIn, router]);

  return (
    <div className="min-h-dvh bg-background">
      <section
        className="relative isolate overflow-hidden bg-gradient-to-br from-hero-from via-hero-via to-hero-to pb-24 pt-safe text-hero-ink"
        style={{ backgroundImage: "linear-gradient(135deg, var(--hero-from), var(--hero-via), var(--hero-to))" }}
      >
        <motion.div
          className="absolute -right-24 -top-24 size-80 rounded-full bg-hero-ink/10 blur-2xl"
          animate={{ scale: [1, 1.08, 1] }}
          transition={{ duration: 9, repeat: Infinity, ease: "easeInOut" }}
          aria-hidden
        />
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
          <Wordmark className="[&_span]:text-hero-ink" />
          <div className="flex items-center gap-2 sm:gap-3">
            <ThemeToggle onHero />
            <LinkButton href="/pricing" variant="ghost" size="sm" className="text-hero-ink hover:bg-hero-ink/10">
              Pricing
            </LinkButton>
            <LinkButton href="/login" variant="ghost" size="sm" className="text-hero-ink hover:bg-hero-ink/10">
              Sign in
            </LinkButton>
          </div>
        </div>
        <motion.div variants={stagger} initial="hidden" animate="show" className="mx-auto max-w-5xl px-6 pt-10 sm:pt-16">
          <motion.p variants={fadeUp} className="inline-flex items-center gap-1.5 rounded-pill bg-hero-ink/15 px-3 py-1 text-sm font-semibold">
            <Leaf className="size-4" aria-hidden /> Neuro-symbolic meal planning
          </motion.p>
          <motion.h1 variants={fadeUp} className="mt-5 max-w-3xl text-4xl font-bold leading-[1.08] tracking-tight sm:text-6xl">
            Meals that fit your life, with reasons you can read.
          </motion.h1>
          <motion.p variants={fadeUp} className="mt-5 max-w-xl text-lg opacity-90">
            Savora is an academic prototype for seven-day planning and meal swaps, with
            explanations. Nutrient targets and clinical or allergy safety are not verified.
          </motion.p>
          <motion.div variants={fadeUp} className="mt-8 flex flex-wrap gap-3">
            <LinkButton href="/register" size="lg" className="bg-hero-ink text-hero-from shadow-float hover:bg-hero-ink/90" icon={<ArrowRight className="size-5" aria-hidden />}>
              Get started
            </LinkButton>
            <LinkButton href="/pricing" size="lg" variant="ghost" className="text-hero-ink ring-1 ring-hero-ink/40 hover:bg-hero-ink/10">
              View pricing
            </LinkButton>
          </motion.div>
        </motion.div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-16 sm:py-24">
        <h2 className="text-center text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Built for how people really eat
        </h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(({ Icon, title, text }) => (
            <div key={title} className="rounded-card border border-border/70 bg-surface p-5 shadow-card">
              <span className="grid size-11 place-items-center rounded-2xl bg-primary-soft text-primary-soft-foreground">
                <Icon className="size-5" aria-hidden />
              </span>
              <h3 className="mt-4 font-semibold">{title}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Side-by-side Pricing Preview Section */}
      <section className="border-t border-border/70 bg-surface-muted/30 py-16 sm:py-24">
        <div className="mx-auto max-w-5xl px-6">
          <div className="text-center">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Transparent pricing
            </h2>
            <p className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
              Simple plans for everyday wellness
            </p>
          </div>

          <div className="mt-10 grid gap-6 sm:grid-cols-2">
            {/* Free */}
            <div className="flex flex-col justify-between rounded-card-lg border border-border/80 bg-surface p-6 shadow-card">
              <div>
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-bold">Free</h3>
                  <span className="rounded-pill bg-surface-muted px-2.5 py-0.5 text-xs font-semibold text-muted-foreground">
                    S$0
                  </span>
                </div>
                <div className="mt-4 rounded-xl bg-surface-muted p-3 text-sm font-semibold text-foreground">
                  Meal discovery, limited weekly plans
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  Explore custom cravings, search safe dishes, and generate baseline 7-day schedules.
                </p>
              </div>
              <div className="mt-6">
                <LinkButton href="/register" variant="secondary" size="md" block>
                  Get started free
                </LinkButton>
              </div>
            </div>

            {/* Premium */}
            <div className="relative flex flex-col justify-between rounded-card-lg border-2 border-primary bg-surface p-6 shadow-float">
              <span className="absolute -top-3 right-6 inline-flex items-center gap-1 rounded-pill bg-primary px-3 py-0.5 text-xs font-bold text-primary-foreground shadow-glow">
                <Zap className="size-3" aria-hidden /> Most Popular
              </span>
              <div>
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-bold">Premium</h3>
                  <span className="text-xl font-bold text-primary-strong dark:text-primary-soft-foreground">
                    S$6.90<span className="text-xs font-normal text-muted-foreground">/month</span>
                  </span>
                </div>
                <div className="mt-4 rounded-xl bg-primary-soft p-3 text-sm font-semibold text-primary-soft-foreground">
                  Advanced preferences, more planning and substitution features
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  Unlock strict multi-cuisine policies, single-slot locked meal swaps, and unlimited plans.
                </p>
              </div>
              <div className="mt-6">
                <LinkButton href="/pricing" variant="primary" size="md" block icon={<ArrowRight className="size-4" aria-hidden />}>
                  View full plan details
                </LinkButton>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/70 py-8 text-center text-xs text-muted-foreground">
        <div className="mx-auto max-w-5xl px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <Wordmark />
          <p>Savora GC1 &middot; Singapore &middot; Free (S$0) &amp; Premium (S$6.90/month)</p>
          <div className="flex items-center gap-4">
            <Link href="/" className="hover:text-foreground">Home</Link>
            <Link href="/pricing" className="hover:text-foreground font-medium">Pricing</Link>
            <Link href="/login" className="hover:text-foreground">Sign in</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
