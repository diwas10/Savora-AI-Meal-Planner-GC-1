"use client";

import { CalendarPlus, ChevronDown, History, Lock, TriangleAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/functional/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { SafetyNotice } from "@/components/ui/SafetyNotice";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState, ErrorState, InlineAlert } from "@/components/ui/States";
import { useProfileQuery } from "@/core/private/UserProfile/service/profile.query";
import { useOnline } from "@/hooks/useOnline";
import { MEAL_ORDER, isoDate, localDate, parseSlot, relativeTime, shortRange } from "@/lib/format";
import { quick, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { MealPlanSummaryDto, PlannedMeal } from "../service/meal-planning.api";
import { selectPlans, useMealPlanDetailQuery, useMealPlansQuery } from "../service/meal-planning.query";
import { DaySelector } from "./DaySelector";
import { GeneratePanel, GeneratingCard } from "./GeneratePanel";
import { MealCard } from "./MealCard";
import { MealDetailSheet } from "./MealDetailSheet";
import { NutritionSummary } from "./NutritionSummary";
import { SwapSheet } from "./SwapSheet";

const NOT_READY_TITLE: Record<string, string> = {
  INFEASIBLE: "No week satisfied every rule",
  INSUFFICIENT_DATA: "Not enough meals for a full week",
  TIMEOUT: "The planner ran out of time",
  FAILED: "This plan could not be generated",
};

function weekDates(weekStart: string): string[] {
  const start = localDate(weekStart);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return isoDate(d);
  });
}

export function MyPlanView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const online = useOnline();
  const plans = useMealPlansQuery();
  const profile = useProfileQuery();
  const { current } = selectPlans(plans.data);
  const selectedId = params.get("plan") ?? current?.id ?? plans.data?.[0]?.id ?? null;
  const detail = useMealPlanDetailQuery(selectedId);
  const plan = detail.data;

  const dates = useMemo(() => (plan ? weekDates(plan.weekStart) : []), [plan]);
  const todayIndex = dates.indexOf(isoDate(new Date()));
  const [day, setDay] = useState<number | null>(null);
  const activeDay = day ?? (todayIndex >= 0 ? todayIndex + 1 : 1);

  const [pickerOpen, setPickerOpen] = useState(false);
  const [newOpen, setNewOpen] = useState(false);
  const [openMeal, setOpenMeal] = useState<PlannedMeal | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [swapMeal, setSwapMeal] = useState<PlannedMeal | null>(null);
  const [swapOpen, setSwapOpen] = useState(false);
  const [swapText, setSwapText] = useState("");

  const selectPlan = useCallback(
    (id: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (id) next.set("plan", id);
      else next.delete("plan");
      next.delete("swap");
      next.delete("text");
      router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
    },
    [params, pathname, router],
  );

  // Hand-off from Discover: /meal-plans?swap=D2_LUNCH&text=something+thai
  const swapSlot = params.get("swap");
  useEffect(() => {
    if (!swapSlot || !plan?.isCurrent) return;
    const meal = plan.slots?.find((s) => s.slotId === swapSlot)?.snapshot;
    const slot = parseSlot(swapSlot);
    if (!meal || !slot) return;
    // Opening a sheet in response to the URL is the external event here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDay(slot.day);
    setSwapText(params.get("text") ?? "");
    setSwapMeal(meal);
    setSwapOpen(true);
    const next = new URLSearchParams(params.toString());
    next.delete("swap");
    next.delete("text");
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }, [swapSlot, plan, params, pathname, router]);

  const meals = (plan?.slots ?? [])
    .map((s) => s.snapshot)
    .filter((m) => m.dayIndex === activeDay)
    .sort((a, b) => MEAL_ORDER.indexOf(a.mealType) - MEAL_ORDER.indexOf(b.mealType));
  const totals = plan?.dayTotals?.find((d) => d.dayIndex === activeDay)?.totals;
  const canSwap = Boolean(plan?.isCurrent && plan.status === "FEASIBLE" && online);

  const openSwap = (meal: PlannedMeal) => {
    setSwapText("");
    setSwapMeal(meal);
    setSwapOpen(true);
  };

  return (
    <>
      <PageHeader
        title="My Plan"
        description={plan ? `${shortRange(plan.weekStart)} · version ${plan.revision}` : "Your saved 7-day plans"}
        action={
          <Button size="sm" variant="secondary" onClick={() => setNewOpen(true)} icon={<CalendarPlus className="size-4" aria-hidden />}>
            New plan
          </Button>
        }
      />

      {plans.isPending ? (
        <PlanSkeleton />
      ) : plans.isError ? (
        <Card>
          <ErrorState message="We couldn't load your plans." offline={!online} onRetry={() => void plans.refetch()} />
        </Card>
      ) : !plans.data?.length ? (
        <GeneratePanel onStarted={(id) => selectPlan(id)} />
      ) : (
        <div className="flex flex-col gap-5">
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            className="flex items-center gap-3 rounded-card bg-surface p-4 text-left shadow-card ring-1 ring-border/70 transition-colors hover:bg-surface-muted"
            aria-haspopup="dialog"
          >
            <History className="size-5 shrink-0 text-muted-foreground" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-muted-foreground">Viewing</p>
              <p className="truncate font-semibold">
                {plan ? `${shortRange(plan.weekStart)}${plan.isCurrent ? " · current" : ""}` : "Loading…"}
              </p>
            </div>
            {plan && <StatusBadge status={plan.status} />}
            <ChevronDown className="size-5 text-muted-foreground" aria-hidden />
          </button>

          {detail.isPending ? (
            <PlanSkeleton />
          ) : detail.isError || !plan ? (
            <Card>
              <ErrorState message="We couldn't load this plan." offline={!online} onRetry={() => void detail.refetch()} />
            </Card>
          ) : plan.status === "GENERATING" ? (
            <GeneratingCard since={plan.createdAt} />
          ) : plan.status !== "FEASIBLE" ? (
            <Card>
              <EmptyState
                icon={<TriangleAlert className="size-7" aria-hidden />}
                title={NOT_READY_TITLE[plan.status] ?? "Plan not ready"}
                description={
                  <>
                    {plan.message}
                    <br />
                    Nothing was saved for this week. Adjusting cuisines or exclusions in your profile can help.
                  </>
                }
                action={
                  <Button onClick={() => setNewOpen(true)} icon={<CalendarPlus className="size-4" aria-hidden />}>
                    Try a new plan
                  </Button>
                }
              />
            </Card>
          ) : (
            <>
              <DaySelector dates={dates} selected={activeDay} onSelect={setDay} idPrefix="plan" />
              {!plan.isCurrent && (
                <InlineAlert tone="info" icon={<Lock className="size-4" aria-hidden />}>
                  This is an earlier version, kept for reference. Swaps work on your current plan.
                </InlineAlert>
              )}
              <section id="plan-panel" role="tabpanel" aria-labelledby={`plan-tab-${activeDay}`} className="flex flex-col gap-5">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div
                    key={activeDay}
                    initial={{ opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -12 }}
                    transition={quick}
                  >
                    <motion.div variants={stagger} initial="hidden" animate="show" className="flex flex-col gap-4 pt-2">
                      {meals.map((meal) => (
                        <MealCard
                          key={meal.slotId}
                          meal={meal}
                          onOpen={() => {
                            setOpenMeal(meal);
                            setDetailOpen(true);
                          }}
                          onSwap={canSwap ? () => openSwap(meal) : undefined}
                        />
                      ))}
                    </motion.div>
                  </motion.div>
                </AnimatePresence>
                <NutritionSummary totals={totals} targets={profile.data?.targets} />
              </section>
              <div className="flex flex-wrap gap-2">
                {plan.fallbackReason === "MODEL_UNAVAILABLE" && <Badge tone="info">Ranked by popularity</Badge>}
                {plan.search && <Badge>Week checked in {plan.search.seconds.toFixed(0)} s</Badge>}
                <Badge>Catalogue {plan.catalogueVersion}</Badge>
              </div>
              <SafetyNotice safety={plan.safety} />
            </>
          )}
        </div>
      )}

      <PlanPicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        plans={plans.data ?? []}
        selectedId={selectedId}
        onSelect={(id) => {
          setPickerOpen(false);
          setDay(null);
          selectPlan(id);
        }}
      />

      <Sheet open={newOpen} onOpenChange={setNewOpen} title="New 7-day plan" description="Your earlier plans are kept.">
        <GeneratePanel
          compact
          onStarted={(id) => {
            setNewOpen(false);
            setDay(null);
            selectPlan(id);
          }}
        />
      </Sheet>

      <MealDetailSheet
        meal={openMeal}
        safety={plan?.safety}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onSwap={
          canSwap && openMeal
            ? () => {
                setDetailOpen(false);
                openSwap(openMeal);
              }
            : undefined
        }
      />
      {plan && swapMeal && (
        <SwapSheet
          // Keyed on the slot only: a finished swap switches the page to the new plan
          // revision, and the sheet must keep showing its result meanwhile.
          key={swapMeal.slotId}
          plan={plan}
          meal={swapMeal}
          open={swapOpen}
          onOpenChange={setSwapOpen}
          initialText={swapText}
          onSwapped={(id) => selectPlan(id)}
        />
      )}
    </>
  );
}

function PlanPicker({
  open,
  onOpenChange,
  plans,
  selectedId,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plans: MealPlanSummaryDto[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Saved plans" description="Every generated plan and swap is kept as its own version.">
      <ul className="flex flex-col gap-2">
        {plans.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              onClick={() => onSelect(p.id)}
              aria-current={p.id === selectedId ? "true" : undefined}
              className={cn(
                "flex w-full items-center gap-3 rounded-2xl bg-surface p-3.5 text-left ring-1 transition-colors hover:bg-surface-muted",
                p.id === selectedId ? "ring-2 ring-primary" : "ring-border",
              )}
            >
              <div className="min-w-0 flex-1">
                <p className="font-semibold">
                  {shortRange(p.weekStart)} <span className="font-normal text-muted-foreground">· v{p.revision}</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  {p.parentPlanId ? "After a meal swap · " : ""}
                  {relativeTime(p.createdAt)}
                </p>
              </div>
              {p.isCurrent && <Badge tone="primary">Current</Badge>}
              <StatusBadge status={p.status} />
            </button>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}

function PlanSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden>
      <div className="flex gap-2">
        {Array.from({ length: 7 }, (_, i) => (
          <Skeleton key={i} className="h-[72px] flex-1" />
        ))}
      </div>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-[104px] rounded-card" />
      ))}
    </div>
  );
}

