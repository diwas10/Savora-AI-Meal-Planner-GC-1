"use client";

import { ArrowRight, CalendarCheck, Leaf, MessageCircle, Repeat2, ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Wordmark } from "@/components/functional/Brand";
import { LinkButton } from "@/components/ui/Button";
import { ThemeToggle } from "@/core/common/theme/ThemeToggle";
import { useIsClient } from "@/hooks/useIsClient";
import { hasSession } from "@/lib/api-request";
import { fadeUp, stagger } from "@/lib/motion";

const FEATURES = [
  { Icon: CalendarCheck, title: "A whole week, checked", text: "21 meals verified together, not one at a time." },
  { Icon: Repeat2, title: "Swap without chaos", text: "Change one meal; the other 20 stay locked." },
  { Icon: MessageCircle, title: "Ask for a craving", text: "“Spicy Thai, no peanuts” in plain words." },
  { Icon: ShieldCheck, title: "Your rules first", text: "Allergies and diet apply to every result." },
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
      <section className="relative isolate overflow-hidden bg-gradient-to-br from-hero-from via-hero-via to-hero-to pb-24 pt-safe text-hero-ink">
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
            Savora plans seven days around your cuisines, diet and allergies, explains every
            choice, and lets you swap a meal without breaking the week.
          </motion.p>
          <motion.div variants={fadeUp} className="mt-8 flex flex-wrap gap-3">
            <LinkButton href="/register" size="lg" className="bg-hero-ink text-hero-from shadow-float hover:bg-hero-ink/90" icon={<ArrowRight className="size-5" aria-hidden />}>
              Get started
            </LinkButton>
            <LinkButton href="/login" size="lg" variant="ghost" className="text-hero-ink ring-1 ring-hero-ink/40 hover:bg-hero-ink/10">
              I have an account
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
    </div>
  );
}
