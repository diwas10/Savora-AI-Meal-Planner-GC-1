"use client";

import { CalendarPlus, ChefHat, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { InlineAlert } from "@/components/ui/States";
import { useOnline } from "@/hooks/useOnline";
import { ApiError } from "@/lib/api-request";
import { nextMonday, shortRange } from "@/lib/format";
import { useCreateMealPlanMutation } from "../service/meal-planning.query";

/** Start a new 7-day plan; earlier plans are kept (never overwritten). */
export function GeneratePanel({
  title = "Generate my 7-day plan",
  description = "21 meals matched to your profile, ranked for you, and checked as a whole week.",
  onStarted,
  compact = false,
}: {
  title?: string;
  description?: string;
  onStarted?: (planId: string) => void;
  compact?: boolean;
}) {
  const [weekStart, setWeekStart] = useState(() => nextMonday());
  const online = useOnline();
  const mutation = useCreateMealPlanMutation();
  const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? "Could not start the plan." : null;

  const start = async () => {
    const res = await mutation.mutateAsync({ weekStart });
    onStarted?.(res.planId);
  };

  return (
    <Card className={compact ? "p-5" : "overflow-hidden p-0"}>
      {!compact && (
        <div className="relative isolate overflow-hidden bg-gradient-to-br from-hero-from via-hero-via to-hero-to px-6 pb-8 pt-7 text-hero-ink">
          <ChefHat className="absolute -right-4 -top-4 size-28 opacity-15 motion-safe:animate-float" aria-hidden />
          <Sparkles className="mb-3 size-7" aria-hidden />
          <h2 className="text-2xl font-bold tracking-tight">{title}</h2>
          <p className="mt-1.5 max-w-md text-[15px] opacity-90">{description}</p>
        </div>
      )}
      <form
        className="flex flex-col gap-4 p-5 sm:flex-row sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          void start();
        }}
      >
        {compact && <h2 className="text-base font-semibold sm:hidden">{title}</h2>}
        <div className="flex flex-1 flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="week-start" className="text-sm font-medium text-foreground">
              Week starts
            </label>
            <span className="text-xs font-normal text-muted-foreground">
              {shortRange(weekStart)}
            </span>
          </div>
          <Input
            id="week-start"
            type="date"
            value={weekStart}
            required
            onChange={(e) => setWeekStart(e.target.value)}
            className="h-12"
          />
        </div>
        <Button
          type="submit"
          size="md"
          className="h-12 w-full rounded-2xl px-6 text-[15px] font-semibold sm:w-auto"
          loading={mutation.isPending}
          disabled={!online}
          icon={<CalendarPlus className="size-5" aria-hidden />}
        >
          {compact ? "Generate" : "Generate plan"}
        </Button>
      </form>
      {(error || !online) && (
        <div className="px-5 pb-5">
          <InlineAlert tone={online ? "danger" : "warning"}>{online ? error : "Planning needs a connection."}</InlineAlert>
        </div>
      )}
    </Card>
  );
}

const STAGES = [
  "Finding meals your profile allows",
  "Ranking them for you",
  "Checking all 21 meals as one week",
];

/** Honest progress: elapsed time and the steps the planner runs; no made-up percentage or stage. */
export function GeneratingCard({ since }: { since: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const seconds = Math.max(0, Math.round((now - new Date(since).getTime()) / 1000));
  const clock = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  return (
    <Card className="overflow-hidden p-6" aria-live="polite" aria-busy="true">
      <div className="flex items-center gap-4">
        <div className="relative grid size-14 shrink-0 place-items-center">
          <span className="absolute inset-0 animate-ping rounded-pill bg-primary-soft motion-reduce:hidden" />
          <span className="relative grid size-14 place-items-center rounded-pill bg-primary text-primary-foreground">
            <ChefHat className="size-7" aria-hidden />
          </span>
        </div>
        <div className="min-w-0">
          <h2 className="text-lg font-semibold">Preparing your week</h2>
          <p className="text-sm text-muted-foreground">The planner is working on it</p>
        </div>
        <span className="ml-auto font-mono text-sm tabular-nums text-muted-foreground" aria-label={`${seconds} seconds elapsed`}>
          {clock}
        </span>
      </div>
      <div className="mt-5 h-1.5 overflow-hidden rounded-pill bg-surface-muted" aria-hidden>
        <div className="skeleton h-full w-full rounded-pill" />
      </div>
      <motion.ol
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.12 } } }}
        className="mt-4 flex flex-col gap-1.5 text-sm"
      >
        {STAGES.map((s, i) => (
          <motion.li key={s} variants={{ hidden: { opacity: 0, x: -6 }, show: { opacity: 1, x: 0 } }} className="flex items-center gap-2 text-muted-foreground">
            <span className="grid size-5 place-items-center rounded-pill bg-surface-muted text-[11px] font-semibold">{i + 1}</span>
            {s}
          </motion.li>
        ))}
      </motion.ol>
      <p className="mt-3 text-xs text-muted-foreground">
        This usually takes 2–3 minutes. You can leave this screen; your plan appears here when it&apos;s ready.
      </p>
    </Card>
  );
}
