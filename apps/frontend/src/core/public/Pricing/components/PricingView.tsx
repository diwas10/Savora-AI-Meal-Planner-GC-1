"use client";

import {
  ArrowRight,
  Check,
  HelpCircle,
  Leaf,
  Repeat2,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { Wordmark } from "@/components/functional/Brand";
import { Badge } from "@/components/ui/Badge";
import { LinkButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ThemeToggle } from "@/core/common/theme/ThemeToggle";
import { useIsClient } from "@/hooks/useIsClient";
import { hasSession } from "@/lib/api-request";
import { fadeUp, stagger } from "@/lib/motion";

interface PlanTier {
  id: "free" | "premium";
  name: string;
  badge?: string;
  price: string;
  cadence: string;
  summary: string;
  description: string;
  primaryAction: {
    label: string;
    href: string;
    variant: "primary" | "secondary";
  };
  highlighted?: boolean;
  features: {
    text: string;
    included: boolean;
    emphasis?: boolean;
  }[];
}

const PLANS: PlanTier[] = [
  {
    id: "free",
    name: "Free",
    price: "S$0",
    cadence: "forever",
    summary: "Meal discovery, limited weekly plans",
    description:
      "Essential tools to explore personalized recipes, test craving queries, and generate baseline weekly plans.",
    primaryAction: {
      label: "Get started free",
      href: "/register",
      variant: "secondary",
    },
    highlighted: false,
    features: [
      { text: "Meal discovery with natural-language cravings", included: true, emphasis: true },
      { text: "Limited weekly plans (1 active 7-day plan)", included: true, emphasis: true },
      { text: "Standard daily macronutrient overview", included: true },
      { text: "Core dietary and common allergen exclusions", included: true },
      { text: "Web & mobile PWA access", included: true },
      { text: "Advanced preferences & multi-cuisine policies", included: false },
      { text: "Locked-slot single meal substitution", included: false },
      { text: "Unlimited plan revisions and version archive", included: false },
      { text: "Deep micronutrient target breakdown", included: false },
    ],
  },
  {
    id: "premium",
    name: "Premium",
    badge: "Most Popular",
    price: "S$6.90",
    cadence: "/ month",
    summary: "Advanced preferences, more planning and substitution features",
    description:
      "Full access to the neuro-symbolic solver, intelligent locked-slot substitutions, and deep nutritional customization.",
    primaryAction: {
      label: "Upgrade to Premium",
      href: "/register?plan=premium",
      variant: "primary",
    },
    highlighted: true,
    features: [
      { text: "Meal discovery with priority AI grounding", included: true },
      { text: "Unlimited 7-day meal plans & saved versions", included: true, emphasis: true },
      { text: "Advanced preferences: multi-cuisine weighting & health goals", included: true, emphasis: true },
      { text: "More planning and substitution features (locked 20 slots)", included: true, emphasis: true },
      { text: "Rule-backed explainability for every suggestion", included: true },
      { text: "Detailed micronutrient & target breakdown", included: true },
      { text: "Custom ingredient bans & strict dietary policies", included: true },
      { text: "Offline plan caching & instant offline sync", included: true },
      { text: "Cancel anytime with no lock-in contract", included: true },
    ],
  },
];

const COMPARISON_ROWS = [
  {
    feature: "Pricing",
    free: "S$0",
    premium: "S$6.90/month",
  },
  {
    feature: "Primary focus",
    free: "Meal discovery, limited weekly plans",
    premium: "Advanced preferences, more planning and substitution features",
  },
  {
    feature: "7-day plan generation",
    free: "1 active plan",
    premium: "Unlimited versions & history",
  },
  {
    feature: "Intelligent meal substitution",
    free: "Basic re-roll",
    premium: "Full CSP solver with 20 slots locked",
  },
  {
    feature: "Craving discovery search",
    free: "Standard query limits",
    premium: "Priority semantic grounding",
  },
  {
    feature: "Cuisine & ingredient filters",
    free: "Standard profiles",
    premium: "Strict, majority & custom rules",
  },
  {
    feature: "Nutrient target breakdown",
    free: "Energy & macros",
    premium: "Full macro & micronutrient ranges",
  },
  {
    feature: "Offline access (PWA)",
    free: "Cached current plan",
    premium: "Full offline sync & history",
  },
];

const FAQS = [
  {
    q: "Why are prices listed in S$ (Singapore Dollars)?",
    a: "Savora was built and benchmarked around regional culinary diversity and research in Singapore, with all prices denominated in Singapore Dollars (SGD).",
  },
  {
    q: "Can I try Savora for free before upgrading?",
    a: "Yes. Our Free tier gives you full access to meal discovery and basic weekly planning with S$0 forever and no credit card required.",
  },
  {
    q: "What does 'locked-slot substitution' mean in Premium?",
    a: "When you want to change dinner on Wednesday, Savora's solver replaces only that single slot while keeping your other 20 planned meals completely locked and verifying weekly nutritional balance.",
  },
  {
    q: "Can I cancel my Premium subscription at any time?",
    a: "Yes, you can cancel at any time directly in your account settings. You will retain Premium benefits until the end of your billing cycle.",
  },
];

export function PricingView() {
  const isClient = useIsClient();
  const signedIn = isClient && hasSession();

  return (
    <div className="min-h-dvh bg-background text-foreground">
      {/* Top Header */}
      <header className="border-b border-border/70 bg-surface/75 backdrop-blur-xl sticky top-0 z-40">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link href={signedIn ? "/dashboard" : "/"} aria-label="Savora home">
            <Wordmark />
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            <ThemeToggle />
            {signedIn ? (
              <LinkButton href="/dashboard" size="sm" variant="secondary">
                Dashboard
              </LinkButton>
            ) : (
              <>
                <LinkButton href="/login" size="sm" variant="ghost">
                  Sign in
                </LinkButton>
                <LinkButton href="/register" size="sm" variant="primary">
                  Get started
                </LinkButton>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section
        className="relative isolate overflow-hidden bg-gradient-to-br from-hero-from via-hero-via to-hero-to px-6 py-16 text-hero-ink sm:py-20"
        style={{
          backgroundImage:
            "linear-gradient(135deg, var(--hero-from), var(--hero-via), var(--hero-to))",
        }}
      >
        <motion.div
          className="absolute -right-20 -top-20 size-80 rounded-full bg-hero-ink/10 blur-3xl pointer-events-none"
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          aria-hidden
        />
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-1.5 rounded-pill bg-hero-ink/15 px-3.5 py-1 text-xs font-semibold tracking-wide uppercase"
          >
            <Sparkles className="size-3.5" aria-hidden /> Transparent & Simple Plans
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="mt-4 text-3xl font-bold tracking-tight sm:text-5xl"
          >
            Invest in meals designed for your body.
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mx-auto mt-4 max-w-2xl text-base opacity-90 sm:text-lg"
          >
            Start free with recipe discovery and weekly planning, or upgrade to Premium for
            advanced preferences, full substitution control, and explainable AI solvers.
          </motion.p>
        </div>
      </section>

      {/* Main Content Area */}
      <main className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16">
        {/* Side-by-side Pricing Cards */}
        <motion.div
          variants={stagger}
          initial="hidden"
          animate="show"
          className="grid gap-6 md:grid-cols-2 lg:gap-8"
        >
          {PLANS.map((plan) => {
            const isHighlight = plan.highlighted;
            return (
              <motion.div
                key={plan.id}
                variants={fadeUp}
                className={`relative flex flex-col justify-between rounded-card-lg p-6 sm:p-8 transition-all ${
                  isHighlight
                    ? "bg-surface shadow-float ring-2 ring-primary dark:ring-primary-strong"
                    : "bg-surface/80 shadow-card ring-1 ring-border/80"
                }`}
              >
                {/* Popular badge */}
                {plan.badge && (
                  <div className="absolute -top-3.5 right-6">
                    <span className="inline-flex items-center gap-1 rounded-pill bg-primary px-3 py-1 text-xs font-bold text-primary-foreground shadow-glow">
                      <Zap className="size-3" aria-hidden /> {plan.badge}
                    </span>
                  </div>
                )}

                <div>
                  <div className="flex items-center justify-between">
                    <h2 className="text-xl font-bold tracking-tight">{plan.name}</h2>
                    {plan.id === "free" ? (
                      <Badge tone="neutral">Free tier</Badge>
                    ) : (
                      <Badge tone="primary">Full access</Badge>
                    )}
                  </div>

                  {/* Price */}
                  <div className="mt-4 flex items-baseline gap-1.5">
                    <span className="text-4xl font-extrabold tracking-tight sm:text-5xl">
                      {plan.price}
                    </span>
                    <span className="text-sm font-medium text-muted-foreground">
                      {plan.cadence}
                    </span>
                  </div>

                  {/* Highlight statement from prompt/screenshot */}
                  <div
                    className={`mt-4 rounded-xl p-3 text-sm font-semibold ${
                      isHighlight
                        ? "bg-primary-soft text-primary-soft-foreground"
                        : "bg-surface-muted text-muted-foreground"
                    }`}
                  >
                    <p>{plan.summary}</p>
                  </div>

                  <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                    {plan.description}
                  </p>

                  {/* Feature Checklist */}
                  <div className="mt-6 border-t border-border/70 pt-6">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      What&apos;s included
                    </p>
                    <ul className="mt-4 space-y-3 text-sm">
                      {plan.features.map((feat) => (
                        <li
                          key={feat.text}
                          className={`flex items-start gap-3 ${
                            feat.included
                              ? "text-foreground"
                              : "text-muted-foreground/60 line-through"
                          }`}
                        >
                          <span
                            className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full text-xs ${
                              feat.included
                                ? isHighlight
                                  ? "bg-primary text-primary-foreground"
                                  : "bg-primary-soft text-primary"
                                : "bg-surface-sunken text-muted-foreground/50"
                            }`}
                          >
                            {feat.included ? (
                              <Check className="size-3" strokeWidth={2.6} />
                            ) : (
                              <span className="size-1 rounded-full bg-current" />
                            )}
                          </span>
                          <span className={feat.emphasis ? "font-semibold" : ""}>
                            {feat.text}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Primary CTA */}
                <div className="mt-8 border-t border-border/70 pt-6">
                  <LinkButton
                    href={signedIn && plan.id === "free" ? "/dashboard" : plan.primaryAction.href}
                    variant={plan.primaryAction.variant}
                    size="lg"
                    block
                    icon={<ArrowRight className="size-4" aria-hidden />}
                  >
                    {signedIn && plan.id === "free"
                      ? "Current tier (Dashboard)"
                      : plan.primaryAction.label}
                  </LinkButton>
                </div>
              </motion.div>
            );
          })}
        </motion.div>

        {/* Feature Comparison Table (matching screenshot table directly) */}
        <section className="mt-16 sm:mt-24">
          <div className="text-center">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              Side-by-side plan comparison
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Review exact capabilities and pricing details side by side.
            </p>
          </div>

          <div className="mt-8 overflow-hidden rounded-card-lg border border-border/80 bg-surface shadow-card">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-surface-muted/60 text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-6 py-4 font-semibold">
                      Plan / Feature
                    </th>
                    <th scope="col" className="px-6 py-4 font-semibold">
                      Free (S$0)
                    </th>
                    <th
                      scope="col"
                      className="px-6 py-4 font-semibold text-primary dark:text-primary-strong"
                    >
                      Premium (S$6.90/mo)
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/70">
                  {COMPARISON_ROWS.map((row, idx) => (
                    <tr
                      key={row.feature}
                      className={
                        idx === 0 || idx === 1
                          ? "bg-primary-soft/15 font-semibold"
                          : "hover:bg-surface-muted/30 transition-colors"
                      }
                    >
                      <td className="px-6 py-4 font-medium text-foreground">
                        {row.feature}
                      </td>
                      <td className="px-6 py-4 text-muted-foreground">
                        {row.free}
                      </td>
                      <td className="px-6 py-4 font-medium text-primary-strong dark:text-primary-soft-foreground">
                        {row.premium}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* Security & Reassurance Banner */}
        <section className="mt-12 rounded-card border border-border/70 bg-surface-muted/40 p-6 sm:p-8">
          <div className="grid gap-6 sm:grid-cols-3">
            <div className="flex items-start gap-3.5">
              <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-primary-soft text-primary">
                <ShieldCheck className="size-5" aria-hidden />
              </span>
              <div>
                <h3 className="text-sm font-semibold">No commitment</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Switch or cancel plans whenever you like directly from your profile.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5">
              <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent">
                <Repeat2 className="size-5" aria-hidden />
              </span>
              <div>
                <h3 className="text-sm font-semibold">Locked-slot swaps</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Swap one dish while keeping all other 20 meals stable and nutritious.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5">
              <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-success-soft text-success">
                <Leaf className="size-5" aria-hidden />
              </span>
              <div>
                <h3 className="text-sm font-semibold">Transparent reasons</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Understand exactly why each food is planned, with explainable rules.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* FAQs */}
        <section className="mt-16 sm:mt-24">
          <div className="text-center">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <HelpCircle className="size-3.5" aria-hidden /> Questions & Answers
            </span>
            <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
              Frequently asked questions
            </h2>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {FAQS.map((faq) => (
              <Card key={faq.q} className="p-5 sm:p-6">
                <h3 className="font-semibold text-foreground">{faq.q}</h3>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                  {faq.a}
                </p>
              </Card>
            ))}
          </div>
        </section>

        {/* Bottom CTA Banner */}
        <section className="mt-16 rounded-sheet bg-gradient-to-br from-hero-from via-hero-via to-hero-to p-8 text-center text-hero-ink shadow-float sm:p-12">
          <h2 className="text-2xl font-bold sm:text-4xl">
            Ready to plan meals that fit your lifestyle?
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-base opacity-90">
            Join Savora today. Start on our Free tier or upgrade to Premium for complete
            algorithmic control.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <LinkButton
              href="/register"
              size="lg"
              className="bg-hero-ink text-hero-from shadow-float hover:bg-hero-ink/90"
              icon={<ArrowRight className="size-5" aria-hidden />}
            >
              Get started now
            </LinkButton>
            <LinkButton
              href={signedIn ? "/dashboard" : "/login"}
              size="lg"
              variant="ghost"
              className="text-hero-ink ring-1 ring-hero-ink/40 hover:bg-hero-ink/10"
            >
              {signedIn ? "Go to dashboard" : "I have an account"}
            </LinkButton>
          </div>
        </section>
      </main>

      {/* Simple Footer */}
      <footer className="border-t border-border/70 py-8 text-center text-xs text-muted-foreground">
        <div className="mx-auto max-w-5xl px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <Wordmark />
          <p>
            Savora GC1 &middot; Singapore &middot; Free (S$0) &amp; Premium (S$6.90/month)
          </p>
          <div className="flex items-center gap-4">
            <Link href="/" className="hover:text-foreground">
              Home
            </Link>
            <Link href="/pricing" className="font-medium text-foreground">
              Pricing
            </Link>
            <Link href="/login" className="hover:text-foreground">
              Sign in
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
