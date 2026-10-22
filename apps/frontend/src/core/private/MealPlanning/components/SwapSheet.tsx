"use client";

import type { Schema } from "@savora/contracts";
import { ArrowDown, ArrowLeft, CircleCheck, Lock, Repeat2, Search, Sparkles, TriangleAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { SuggestionChip } from "@/components/ui/Chip";
import { Textarea } from "@/components/ui/Field";
import { MealArt } from "@/components/ui/MealArt";
import { SafetyNotice } from "@/components/ui/SafetyNotice";
import { Sheet } from "@/components/ui/Sheet";
import { InlineAlert } from "@/components/ui/States";
import { ApiError } from "@/lib/api-request";
import { FLAVOR_LABEL, MEAL_LABEL, cuisineLabel, ingredientLabel, longDate, nutrient } from "@/lib/format";
import { fadeUp, quick, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { mealTitle } from "../lib/meal";
import {
  useCreateSubstitutionMutation,
  useReplacementOptionsMutation,
  useSubstitutionQuery,
} from "../service/meal-planning.query";
import type { MealPlanDetailDto, PlannedMeal, ReplacementOptionsDto } from "../service/meal-planning.api";

type CravingRequest = Schema<"CravingRequest">;
type Step = "ask" | "choose" | "checking" | "done"; // "done" is derived, never set

const PROMPTS = ["Something spicy", "Something creamy", "No potato", "No rice", "Something lighter"];

interface SwapSheetProps {
  plan: MealPlanDetailDto;
  meal: PlannedMeal | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialText?: string;
  onSwapped: (newPlanId: string) => void;
}

function preferenceChips(preference: CravingRequest | null | undefined): string[] {
  if (!preference) return [];
  return [
    ...(preference.cuisineIds ?? []).map(cuisineLabel),
    ...(preference.flavorTags ?? []).map((f) => FLAVOR_LABEL[f]),
    ...(preference.excludedIngredientIds ?? []).map((x) => `no ${ingredientLabel(x)}`),
  ];
}

export function SwapSheet({ plan, meal, open, onOpenChange, initialText = "", onSwapped }: SwapSheetProps) {
  const slotId = meal?.slotId ?? "D1_BREAKFAST";
  const [step, setStep] = useState<Step>("ask");
  const [text, setText] = useState(initialText);
  const [options, setOptions] = useState<ReplacementOptionsDto | null>(null);
  const [choice, setChoice] = useState<string | null>(null);
  const [excluded, setExcluded] = useState<string[]>([]);
  const [substitutionId, setSubstitutionId] = useState<string | null>(null);
  const reported = useRef<string | null>(null);

  const optionsMutation = useReplacementOptionsMutation(plan.id, slotId);
  const swapMutation = useCreateSubstitutionMutation(plan.id);
  const swapQuery = useSubstitutionQuery(substitutionId);
  const sub = swapQuery.data;

  // "checking" becomes "done" as soon as the polled swap settles.
  const settled = sub !== undefined && sub.status !== "GENERATING";
  const view: Step = step === "checking" && settled ? "done" : step;

  // Hand a finished swap to the page once, even if the sheet was closed meanwhile.
  useEffect(() => {
    if (sub?.status === "FEASIBLE" && sub.toPlanId && reported.current !== sub.id) {
      reported.current = sub.id;
      onSwapped(sub.toPlanId);
    }
  }, [sub, onSwapped]);

  if (!meal) return null;
  const { title } = mealTitle(meal.explanation);
  const label = MEAL_LABEL[meal.mealType];

  const findOptions = async (words: string) => {
    setChoice(null);
    const result = await optionsMutation.mutateAsync({
      preferenceText: words.trim() || null,
      excludeCombinationIds: excluded,
    });
    setOptions(result);
    setChoice(result.result.options[0]?.combinationId ?? null);
    setStep("choose");
  };

  const startSwap = async () => {
    if (!choice) return;
    const accepted = await swapMutation.mutateAsync({
      slotId,
      expectedRevision: plan.revision,
      replacementCombinationId: choice,
      excludeCombinationIds: excluded,
    });
    setSubstitutionId(accepted.substitutionId);
    setStep("checking");
  };

  const tryAnother = () => {
    if (choice) setExcluded((prev) => [...new Set([...prev, choice])]);
    setSubstitutionId(null);
    setStep("ask");
  };

  const reset = (next: boolean) => {
    onOpenChange(next);
    if (!next && view !== "checking") {
      setStep("ask");
      setOptions(null);
      setSubstitutionId(null);
      setExcluded([]);
    }
  };

  const error = optionsMutation.error ?? swapMutation.error;
  const errorMessage = error instanceof ApiError ? error.message : error ? "Something went wrong. Please try again." : null;
  const chips = preferenceChips(options?.result.preference);
  const after = sub?.afterSnapshot;

  return (
    <Sheet
      open={open}
      onOpenChange={reset}
      title={`Swap ${label.toLowerCase()}`}
      description={`${longDate(meal.calendarDate)} · now: ${title}`}
    >
      <AnimatePresence mode="wait" initial={false}>
        {view === "ask" && (
          <motion.div key="ask" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={quick} className="flex flex-col gap-4">
            <InlineAlert tone="info" icon={<Lock className="size-4" aria-hidden />}>
              Your other 20 meals stay locked. The new meal is checked against the whole week
              before anything is saved.
            </InlineAlert>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void findOptions(text);
              }}
              className="flex flex-col gap-3"
            >
              <label htmlFor="swap-text" className="text-sm font-medium">
                What would you like instead? <span className="font-normal text-muted-foreground">(optional)</span>
              </label>
              <Textarea
                id="swap-text"
                value={text}
                maxLength={500}
                onChange={(e) => setText(e.target.value)}
                placeholder="e.g. something spicy, no potato"
                className="min-h-20"
              />
              <div className="scrollbar-none -mx-5 flex gap-2 overflow-x-auto px-5">
                {PROMPTS.map((p) => (
                  <SuggestionChip key={p} onClick={() => setText(p)}>
                    {p}
                  </SuggestionChip>
                ))}
              </div>
              {errorMessage && <InlineAlert tone="danger">{errorMessage}</InlineAlert>}
              <Button type="submit" size="lg" block loading={optionsMutation.isPending} icon={<Search className="size-5" aria-hidden />}>
                Show eligible meals
              </Button>
            </form>
          </motion.div>
        )}

        {view === "choose" && options && (
          <motion.div key="choose" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={quick} className="flex flex-col gap-4">
            <button type="button" onClick={() => setStep("ask")} className="inline-flex w-fit items-center gap-1 text-sm font-medium text-primary">
              <ArrowLeft className="size-4" aria-hidden /> Change request
            </button>
            {chips.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5" aria-label="How your words were read">
                <Sparkles className="size-4 text-accent" aria-hidden />
                {chips.map((c) => (
                  <Badge key={c} tone="accent">
                    {c}
                  </Badge>
                ))}
              </div>
            )}
            <p className="text-sm text-muted-foreground">{options.result.message}</p>
            {options.result.unmatchedFlavorTags.length > 0 && (
              <InlineAlert tone="warning">
                No eligible meal is {options.result.unmatchedFlavorTags.map((f) => FLAVOR_LABEL[f].toLowerCase()).join(" or ")}; that part was relaxed.
              </InlineAlert>
            )}
            {options.result.options.length === 0 ? (
              <InlineAlert tone="warning" icon={<TriangleAlert className="size-4" aria-hidden />} title="No eligible meal">
                Nothing matches this request alongside your profile rules and the rest of the week.
                Try different words, or none at all.
              </InlineAlert>
            ) : (
              <fieldset>
                <legend className="sr-only">Choose a replacement</legend>
                <motion.ul variants={stagger} initial="hidden" animate="show" className="flex flex-col gap-2.5">
                  {options.result.options.map((option) => {
                    const t = mealTitle(option.explanation);
                    const selected = option.combinationId === choice;
                    return (
                      <motion.li key={option.combinationId} variants={fadeUp}>
                        <label
                          className={cn(
                            "flex cursor-pointer items-center gap-3 rounded-2xl bg-surface p-3 ring-1 transition-shadow has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                            selected ? "ring-2 ring-primary" : "ring-border",
                          )}
                        >
                          <input
                            type="radio"
                            name="replacement"
                            className="sr-only"
                            checked={selected}
                            onChange={() => setChoice(option.combinationId)}
                          />
                          <MealArt mealType={meal.mealType} label="" size="sm" />
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-semibold">{t.title}</p>
                            {t.withText && <p className="truncate text-sm text-muted-foreground">{t.withText}</p>}
                            <div className="mt-1 flex flex-wrap items-center gap-1.5">
                              <span className="text-sm font-medium tabular-nums">{nutrient(option.explanation.totals.energyKcal, "kcal")}</span>
                              {option.cuisines.slice(0, 2).map((c) => (
                                <Badge key={c}>{c}</Badge>
                              ))}
                              {option.rank === 1 && <Badge tone="primary">Top ranked</Badge>}
                            </div>
                          </div>
                          <span
                            aria-hidden
                            className={cn(
                              "grid size-6 shrink-0 place-items-center rounded-pill ring-2",
                              selected ? "bg-primary ring-primary" : "ring-border-strong",
                            )}
                          >
                            {selected && <span className="size-2.5 rounded-pill bg-primary-foreground" />}
                          </span>
                        </label>
                      </motion.li>
                    );
                  })}
                </motion.ul>
              </fieldset>
            )}
            {options.result.fallbackReason === "MODEL_UNAVAILABLE" && (
              <p className="text-xs text-muted-foreground">Ranked by popularity (the personal ranking model is not installed).</p>
            )}
            <SafetyNotice safety={options.result.safety} compact />
            {errorMessage && <InlineAlert tone="danger">{errorMessage}</InlineAlert>}
            <Button
              size="lg"
              block
              disabled={!choice}
              loading={swapMutation.isPending}
              onClick={() => void startSwap()}
              icon={<Repeat2 className="size-5" aria-hidden />}
            >
              Swap and check my week
            </Button>
          </motion.div>
        )}

        {view === "checking" && (
          <motion.div key="checking" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="flex flex-col items-center py-8 text-center" aria-live="polite">
            <div className="relative mb-6 grid size-24 place-items-center">
              <span className="absolute inset-0 animate-ping rounded-pill bg-primary-soft opacity-60 motion-reduce:hidden" />
              <span className="relative grid size-20 place-items-center rounded-pill bg-primary text-primary-foreground shadow-glow">
                <Repeat2 className="size-8 animate-spin [animation-duration:2.4s]" aria-hidden />
              </span>
            </div>
            <h3 className="text-lg font-semibold">Checking your week</h3>
            <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">
              The new meal is validated with your other 20 meals locked. This can take a couple
              of minutes. You can close this sheet; we&apos;ll update your plan when it&apos;s done.
            </p>
          </motion.div>
        )}

        {view === "done" && sub && (
          <motion.div key="done" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-4" aria-live="polite">
            {sub.status === "FEASIBLE" && after ? (
              <>
                <div className="flex flex-col items-center py-2 text-center">
                  <motion.span initial={{ scale: 0.6 }} animate={{ scale: 1 }} className="grid size-14 place-items-center rounded-pill bg-success-soft text-success">
                    <CircleCheck className="size-8" aria-hidden />
                  </motion.span>
                  <h3 className="mt-3 text-lg font-semibold">Meal swapped</h3>
                  <p className="text-sm text-muted-foreground">Saved as a new version of your plan. Nothing else changed.</p>
                </div>
                <div className="flex flex-col items-stretch gap-2">
                  {sub.beforeSnapshot && <SnapshotRow label="Before" meal={sub.beforeSnapshot} muted />}
                  <ArrowDown className="mx-auto size-4 text-muted-foreground" aria-hidden />
                  <SnapshotRow label="After" meal={after} />
                </div>
                <Button size="lg" block onClick={() => reset(false)}>
                  Done
                </Button>
              </>
            ) : (
              <>
                <InlineAlert tone="warning" icon={<TriangleAlert className="size-4" aria-hidden />} title="This swap didn't fit your week">
                  {sub.message ?? "No feasible replacement."} Your saved plan is unchanged.
                </InlineAlert>
                <Button size="lg" variant="secondary" block onClick={tryAnother}>
                  Try another meal
                </Button>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </Sheet>
  );
}

function SnapshotRow({ label, meal, muted = false }: { label: string; meal: PlannedMeal; muted?: boolean }) {
  const t = mealTitle(meal.explanation);
  return (
    <div className={cn("flex items-center gap-3 rounded-2xl p-3 ring-1 ring-border", muted ? "bg-surface-muted opacity-80" : "bg-surface")}>
      <MealArt mealType={meal.mealType} label="" size="sm" />
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className={cn("truncate font-semibold", muted && "line-through decoration-1")}>{t.title}</p>
        <p className="text-sm tabular-nums text-muted-foreground">{nutrient(meal.explanation.totals.energyKcal, "kcal")}</p>
      </div>
    </div>
  );
}
