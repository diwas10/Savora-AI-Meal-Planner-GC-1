"use client";

import { ArrowRight, CalendarCheck, Leaf, MessageCircle, Repeat2, ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Wordmark } from "@/components/functional/Brand";
import { LinkButton } from "@/components/ui/Button";
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
          <LinkButton href="/login" variant="ghost" size="sm" className="text-hero-ink hover:bg-hero-ink/10">
            Sign in
          </LinkButton>
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
      <motion.ul
        variants={stagger}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
        className="relative mx-auto -mt-12 grid max-w-5xl gap-3 px-6 pb-16 sm:grid-cols-2 lg:grid-cols-4"
      >
        {FEATURES.map(({ Icon, title, text }) => (
          <motion.li key={title} variants={fadeUp} className="rounded-card bg-surface p-5 shadow-card ring-1 ring-border/70">
            <span className="grid size-11 place-items-center rounded-2xl bg-primary-soft text-primary-soft-foreground">
              <Icon className="size-5" aria-hidden />
            </span>
            <h2 className="mt-4 font-semibold">{title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{text}</p>
          </motion.li>
        ))}
      </motion.ul>
      <p className="pb-10 text-center text-xs text-muted-foreground">
        Savora GC1 · planning guidance, not medical advice
      </p>
    </div>
  );
}
