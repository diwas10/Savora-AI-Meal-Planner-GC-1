"use client";

import { ArrowRight, CalendarDays, MessageCircle, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/functional/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { LinkButton } from "@/components/ui/Button";
import { Card, SectionTitle } from "@/components/ui/Card";
import { SafetyNotice } from "@/components/ui/SafetyNotice";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState, InlineAlert } from "@/components/ui/States";
import { useProfileQuery } from "@/core/private/UserProfile/service/profile.query";
import { useCurrentUserQuery } from "@/core/public/Auth/service/auth.query";
import { useOnline } from "@/hooks/useOnline";
import { MEAL_ORDER, greeting, isoDate, localDate, longDate } from "@/lib/format";
import { fadeUp, stagger } from "@/lib/motion";
import type { PlannedMeal } from "../service/meal-planning.api";
import { selectPlans, useMealPlanDetailQuery, useMealPlansQuery } from "../service/meal-planning.query";
import { GeneratePanel, GeneratingCard } from "./GeneratePanel";
import { MealCard } from "./MealCard";
import { MealDetailSheet } from "./MealDetailSheet";
import { NutritionSummary } from "./NutritionSummary";
import { SwapSheet } from "./SwapSheet";

/** Which plan day to show today: today if inside the week, else the nearest end. */
function planDay(weekStart: string, today: string): { day: number; note: string | null } {
  const diff = Math.round((localDate(today).getTime() - localDate(weekStart).getTime()) / 86_400_000);
  if (diff < 0) return { day: 1, note: `Your plan starts ${longDate(weekStart)}.` };
  if (diff > 6) return { day: 7, note: "This plan's week has ended. Generate a new one when you're ready." };
  return { day: diff + 1, note: null };
}

export function HomeView() {
  const user = useCurrentUserQuery();
  const profile = useProfileQuery();
  const plans = useMealPlansQuery();
  const { current, latest, generating } = selectPlans(plans.data);
  const detail = useMealPlanDetailQuery(current?.id);
  const online = useOnline();
  const [openMeal, setOpenMeal] = useState<PlannedMeal | null>(null);
  const [swapMeal, setSwapMeal] = useState<PlannedMeal | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [swapOpen, setSwapOpen] = useState(false);

  const firstName = user.data?.displayName.split(" ")[0] ?? "";
  const today = isoDate(new Date());
  const plan = detail.data;
  const position = plan ? planDay(plan.weekStart, today) : null;
  const meals = (plan?.slots ?? [])
    .map((s) => s.snapshot)
    .filter((m) => m.dayIndex === position?.day)
    .sort((a, b) => MEAL_ORDER.indexOf(a.mealType) - MEAL_ORDER.indexOf(b.mealType));
  const totals = plan?.dayTotals?.find((d) => d.dayIndex === position?.day)?.totals;
  const failedLatest = latest && !latest.isCurrent && latest.status !== "GENERATING" && latest.status !== "FEASIBLE" ? latest : null;

  return (
    <>
      <PageHeader
        eyebrow={longDate(today)}
        title={
          <>
            {greeting()}
            {firstName && <span className="text-primary">, {firstName}</span>}
          </>
        }
        action={
          <Link href="/profile" aria-label="Profile" className="grid size-11 place-items-center rounded-pill bg-primary-soft text-base font-bold text-primary-soft-foreground">
            {firstName.charAt(0).toUpperCase() || "S"}
          </Link>
        }
      />

      <motion.div variants={stagger} initial="hidden" animate="show" className="flex flex-col gap-6">
        {plans.isPending ? (
          <HomeSkeleton />
        ) : plans.isError ? (
          <Card>
            <ErrorState message="We couldn't load your plans." offline={!online} onRetry={() => void plans.refetch()} />
          </Card>
        ) : (
          <>
            {generating && (
              <motion.div variants={fadeUp}>
                <GeneratingCard since={generating.createdAt} />
              </motion.div>
            )}
            {failedLatest && !generating && (
              <motion.div variants={fadeUp}>
                <InlineAlert tone="warning" title="Your last plan could not be completed">
                  {failedLatest.message}
                </InlineAlert>
              </motion.div>
            )}

            {!current && !generating && (
              <motion.div variants={fadeUp}>
                <GeneratePanel />
              </motion.div>
            )}

            {current && detail.isPending && <HomeSkeleton />}
            {current && detail.isError && (
              <Card>
                <ErrorState message="We couldn't load today's meals." offline={!online} onRetry={() => void detail.refetch()} />
              </Card>
            )}

            {plan && position && (
              <>
                <motion.section variants={fadeUp} aria-labelledby="today-meals">
                  <SectionTitle
                    title={position.note ? `Day ${position.day} of your plan` : "Today's planned meals"}
                    action={
                      <Link href="/meal-plans" className="inline-flex items-center gap-1 text-sm font-semibold text-primary">
                        Full week <ArrowRight className="size-4" aria-hidden />
                      </Link>
                    }
                  />
                  <h2 id="today-meals" className="sr-only">
                    Meals
                  </h2>
                  {position.note && <p className="-mt-1 mb-3 text-sm text-muted-foreground">{position.note}</p>}
                  <motion.div variants={stagger} className="flex flex-col gap-3">
                    {meals.map((meal) => (
                      <MealCard
                        key={meal.slotId}
                        meal={meal}
                        onOpen={() => {
                          setOpenMeal(meal);
                          setDetailOpen(true);
                        }}
                      />
                    ))}
                  </motion.div>
                </motion.section>

                <motion.div variants={fadeUp}>
                  <NutritionSummary totals={totals} targets={profile.data?.targets} title={position.note ? "Planned for this day" : "Planned for today"} />
                </motion.div>

                <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-2">
                  <Badge tone="primary">
                    <CalendarDays className="size-3.5" aria-hidden /> Version {plan.revision}
                  </Badge>
                  {plan.fallbackReason === "MODEL_UNAVAILABLE" && <Badge tone="info">Ranked by popularity</Badge>}
                </motion.div>
                <motion.div variants={fadeUp}>
                  <SafetyNotice safety={plan.safety} compact />
                </motion.div>
              </>
            )}

            <motion.div variants={fadeUp}>
              <Card className="flex items-center gap-4 p-5">
                <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent-soft-foreground">
                  <MessageCircle className="size-6" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="font-semibold">Craving something?</h2>
                  <p className="text-sm text-muted-foreground">Tell Savora what you feel like and get dishes your profile allows.</p>
                </div>
                <LinkButton href="/discover" variant="subtle" size="sm" icon={<Sparkles className="size-4" aria-hidden />}>
                  Discover
                </LinkButton>
              </Card>
            </motion.div>
          </>
        )}
      </motion.div>

      <MealDetailSheet
        meal={openMeal}
        safety={plan?.safety}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onSwap={
          plan?.isCurrent
            ? () => {
                setDetailOpen(false);
                setSwapMeal(openMeal);
                setSwapOpen(true);
              }
            : undefined
        }
      />
      {plan && (
        <SwapSheet key={swapMeal?.slotId ?? "none"} plan={plan} meal={swapMeal} open={swapOpen} onOpenChange={setSwapOpen} onSwapped={() => undefined} />
      )}
    </>
  );
}

export function HomeSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden>
      <Skeleton className="h-6 w-48" />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-[104px] rounded-card" />
      ))}
      <Skeleton className="h-44 rounded-card" />
    </div>
  );
}
