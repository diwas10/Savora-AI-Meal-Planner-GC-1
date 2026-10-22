"use client";

import type { Schema } from "@savora/contracts";
import { ChevronRight, Flame, Repeat2 } from "lucide-react";
import { motion } from "motion/react";
import { MealArt } from "@/components/ui/MealArt";
import { MEAL_LABEL, nutrient } from "@/lib/format";
import { fadeUp } from "@/lib/motion";
import { mealTitle } from "../lib/meal";

type PlannedMeal = Schema<"PlannedMeal">;

interface MealCardProps {
  meal: PlannedMeal;
  onOpen: () => void;
  onSwap?: () => void;
}

/**
 * The whole card opens the detail sheet; "Swap" is a separate sibling button so the two
 * actions never conflict (DESIGN_SYSTEM: Meal card).
 */
export function MealCard({ meal, onOpen, onSwap }: MealCardProps) {
  const { title, withText } = mealTitle(meal.explanation);
  const label = MEAL_LABEL[meal.mealType];
  const energy = meal.explanation.totals.energyKcal;
  return (
    <motion.article variants={fadeUp} className="relative">
      <button
        type="button"
        onClick={onOpen}
        className="group flex w-full items-center gap-4 rounded-card bg-surface p-3 pr-4 text-left shadow-card ring-1 ring-border/70 transition-[transform,box-shadow] hover:shadow-float active:scale-[0.99]"
        aria-label={`${label}: ${title}${withText ? ` ${withText}` : ""}. View meal`}
      >
        <MealArt mealType={meal.mealType} label={`${label} illustration`} />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
          <h3 className="mt-0.5 truncate text-base font-semibold leading-snug">{title}</h3>
          {withText && <p className="truncate text-sm text-muted-foreground">{withText}</p>}
          <p className="mt-1.5 flex items-center gap-1 text-sm font-medium text-foreground">
            <Flame className="size-4 text-chart-energy" aria-hidden />
            <span className="tabular-nums">{nutrient(energy, "kcal")}</span>
            <span className="text-xs font-normal text-muted-foreground">planned</span>
          </p>
        </div>
        <ChevronRight className="size-5 shrink-0 text-subtle-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
      </button>
      {onSwap && (
        <button
          type="button"
          onClick={onSwap}
          className="absolute -top-2 right-3 inline-flex h-8 items-center gap-1 rounded-pill bg-surface px-3 text-xs font-semibold text-primary shadow-card ring-1 ring-border transition-colors hover:bg-primary-soft"
        >
          <Repeat2 className="size-3.5" aria-hidden />
          Swap
          <span className="sr-only"> {label}</span>
        </button>
      )}
    </motion.article>
  );
}
