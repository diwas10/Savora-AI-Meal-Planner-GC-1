"use client";

import { CalendarPlus, Check, ChefHat, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { InlineAlert } from "@/components/ui/States";
import { useOnline } from "@/hooks/useOnline";
import { ApiError } from "@/lib/api-request";
import { nextMonday, shortRange } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useCancelMealPlanMutation, useCreateMealPlanMutation } from "../service/meal-planning.query";

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
          <div className="pointer-events-none absolute -right-12 -top-12 size-48 rounded-pill bg-white/10 blur-2xl" />
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-hero-ink/80">
            <Sparkles className="size-4" aria-hidden /> Savora planner
          </div>
          <h2 className="mt-2 text-2xl font-bold tracking-tight">{title}</h2>
          <p className="mt-1 max-w-xl text-sm text-hero-ink/90">{description}</p>
        </div>
      )}

      <div className={compact ? "space-y-4" : "space-y-4 p-6"}>
        {compact && (
          <div>
            <h3 className="font-semibold">{title}</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          </div>
        )}

        <div>
          <label htmlFor="week-start-input" className="text-xs font-medium text-muted-foreground">
            Starting Monday
          </label>
          <div className="mt-1 flex items-center gap-2">
            <Input
              id="week-start-input"
              type="date"
              value={weekStart}
              onChange={(e) => setWeekStart(e.target.value)}
              className="h-11 max-w-xs"
            />
            <span className="text-xs text-muted-foreground">({shortRange(weekStart)})</span>
          </div>
        </div>

        {error && <InlineAlert tone="danger">{error}</InlineAlert>}

        <Button
          block
          size="lg"
          onClick={() => void start()}
          loading={mutation.isPending}
          disabled={!online}
          icon={<CalendarPlus className="size-5" aria-hidden />}
        >
          {online ? "Start 7-day plan" : "Connect to internet to plan"}
        </Button>
      </div>
    </Card>
  );
}

const STAGES = [
  "Finding meals your profile allows",
  "Ranking them for you",
  "Checking all 21 meals as one week",
];

function getEstimatedProgress(seconds: number): number {
  if (seconds <= 8) {
    return 10 + (seconds / 8) * 30; // 10% -> 40%
  }
  if (seconds <= 24) {
    return 40 + ((seconds - 8) / 16) * 48; // 40% -> 88%
  }
  return Math.min(98, 88 + 9 * (1 - Math.exp(-(seconds - 24) / 20)));
}

function getActiveStage(seconds: number): number {
  if (seconds < 8) return 0;
  if (seconds < 16) return 1;
  return 2;
}

/** Honest progress: elapsed time, visual progress bar, and active steps the planner runs. */
export function GeneratingCard({ since, planId }: { since: string; planId?: string }) {
  const [now, setNow] = useState(() => Date.now());
  const cancelMutation = useCancelMealPlanMutation();
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const seconds = Math.max(0, Math.round((now - new Date(since).getTime()) / 1000));
  const clock = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  const progress = getEstimatedProgress(seconds);
  const activeStage = getActiveStage(seconds);

  return (
    <Card className="overflow-hidden p-6" aria-live="polite" aria-busy="true">
      <div className="flex items-center gap-4">
        <div className="relative grid size-14 shrink-0 place-items-center">
          <span className="absolute inset-0 animate-ping rounded-pill bg-primary-soft opacity-75 motion-reduce:hidden" />
          <span className="relative grid size-14 place-items-center rounded-pill bg-primary text-primary-foreground shadow-glow">
            <ChefHat className="size-7" aria-hidden />
          </span>
        </div>
        <div className="min-w-0">
          <h2 className="text-lg font-semibold tracking-tight">Preparing your week</h2>
          <p className="text-sm text-muted-foreground">The planner is working on it</p>
        </div>
        <div className="ml-auto flex items-baseline gap-2 font-mono text-sm tabular-nums">
          <span className="font-semibold text-primary">{Math.round(progress)}%</span>
          <span className="text-xs text-muted-foreground" aria-label={`${seconds} seconds elapsed`}>
            {clock}
          </span>
        </div>
      </div>

      {/* Animated active progress bar */}
      <div
        className="relative mt-5 h-2 w-full overflow-hidden rounded-pill bg-surface-muted ring-1 ring-border/50"
        role="progressbar"
        aria-valuenow={Math.round(progress)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Planning progress"
      >
        <motion.div
          className="relative h-full rounded-pill bg-gradient-to-r from-hero-from via-hero-via to-hero-to shadow-sm"
          initial={false}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          <motion.span
            className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent"
            animate={{ x: ["-100%", "200%"] }}
            transition={{ repeat: Infinity, duration: 1.8, ease: "linear" }}
          />
        </motion.div>
      </div>

      <motion.ol
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.12 } } }}
        className="mt-4 flex flex-col gap-2 text-sm"
      >
        {STAGES.map((s, i) => {
          const isDone = activeStage > i;
          const isCurrent = activeStage === i;
          return (
            <motion.li
              key={s}
              variants={{ hidden: { opacity: 0, x: -6 }, show: { opacity: 1, x: 0 } }}
              className={cn(
                "flex items-center gap-2.5 transition-colors",
                isDone
                  ? "text-foreground font-medium"
                  : isCurrent
                    ? "text-primary font-semibold"
                    : "text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "grid size-5 place-items-center rounded-pill text-[11px] font-semibold transition-colors",
                  isDone
                    ? "bg-primary-soft text-primary-soft-foreground"
                    : isCurrent
                      ? "bg-primary text-primary-foreground ring-2 ring-primary/30"
                      : "bg-surface-muted text-subtle-foreground",
                )}
              >
                {isDone ? <Check className="size-3 stroke-[2.5]" aria-hidden /> : i + 1}
              </span>
              <span>{s}</span>
              {isCurrent && (
                <span className="relative flex size-2 ml-1" aria-hidden>
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75 motion-reduce:hidden" />
                  <span className="relative inline-flex size-2 rounded-full bg-primary" />
                </span>
              )}
            </motion.li>
          );
        })}
      </motion.ol>
      <p className="mt-3 text-xs text-muted-foreground">
        This usually takes 2–3 minutes. You can leave this screen; your plan appears here when it&apos;s ready.
      </p>

      {seconds >= 120 && (
        <div className="mt-4 flex flex-col gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-200">
          <div className="flex items-center justify-between gap-3">
            <span>
              {seconds >= 180
                ? "This generation is taking longer than expected. You can cancel and try again."
                : "Optimizing all 21 meals against clinical and profile targets..."}
            </span>
            {planId && (
              <Button
                variant="secondary"
                size="sm"
                className="shrink-0 h-7 text-xs border-amber-500/30 hover:bg-amber-500/20"
                onClick={() => cancelMutation.mutate(planId)}
                disabled={cancelMutation.isPending}
              >
                {cancelMutation.isPending ? "Cancelling..." : "Cancel & Try Again"}
              </Button>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
