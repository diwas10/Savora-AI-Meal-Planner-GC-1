"use client";

import type { Schema } from "@savora/contracts";
import { CircleCheck, Database, Info, Repeat2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { MealArt } from "@/components/ui/MealArt";
import { SafetyNotice } from "@/components/ui/SafetyNotice";
import { Sheet } from "@/components/ui/Sheet";
import { MEAL_LABEL, NUTRIENT_ROWS, dishName, longDate, nutrient } from "@/lib/format";
import { REASON_LABEL, SOURCE_LABEL, mealTitle, reasonsByKind, roleLabel } from "../lib/meal";

type PlannedMeal = Schema<"PlannedMeal">;
type SafetyVerification = Schema<"SafetyVerification">;

interface MealDetailSheetProps {
  meal: PlannedMeal | null;
  safety?: SafetyVerification | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSwap?: () => void;
}

export function MealDetailSheet({ meal, safety, open, onOpenChange, onSwap }: MealDetailSheetProps) {
  if (!meal) return null;
  const { title, withText } = mealTitle(meal.explanation);
  const exp = meal.explanation;
  const unknown = new Set(exp.unknownNutrients);
  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={`${MEAL_LABEL[meal.mealType]} · ${longDate(meal.calendarDate)}`}
      footer={
        onSwap ? (
          <Button block size="lg" onClick={onSwap} icon={<Repeat2 className="size-5" aria-hidden />}>
            Substitute meal
          </Button>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-6">
        <MealArt mealType={meal.mealType} label={`${MEAL_LABEL[meal.mealType]} illustration`} size="lg" />
        {withText && <p className="-mt-3 text-sm text-muted-foreground">{title} {withText}</p>}

        <section aria-labelledby="meal-dishes">
          <h3 id="meal-dishes" className="mb-2 text-sm font-semibold text-muted-foreground">
            What&apos;s on the plate
          </h3>
          <ul className="divide-y divide-border overflow-hidden rounded-2xl bg-surface ring-1 ring-border">
            {exp.dishes.map((dish) => {
              const name = dishName(dish.name);
              return (
                <li key={dish.dishId} className="flex items-start justify-between gap-3 p-3.5">
                  <div className="min-w-0">
                    <p className="font-medium leading-snug">{name.title}</p>
                    {name.subtitle && <p className="text-xs text-muted-foreground">{name.subtitle}</p>}
                    <p className="mt-1 text-sm text-foreground">{dish.portion}</p>
                  </div>
                  <Badge tone="primary" className="shrink-0">
                    {roleLabel(dish.role)}
                  </Badge>
                </li>
              );
            })}
          </ul>
        </section>

        <section aria-labelledby="meal-nutrients">
          <div className="mb-2 flex items-center justify-between">
            <h3 id="meal-nutrients" className="text-sm font-semibold text-muted-foreground">
              Planned nutrition
            </h3>
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Database className="size-3.5" aria-hidden />
              {SOURCE_LABEL[exp.sourceTier]}
            </span>
          </div>
          <table className="w-full overflow-hidden rounded-2xl bg-surface text-sm ring-1 ring-border">
            <caption className="sr-only">Planned nutrients for this meal</caption>
            <tbody className="divide-y divide-border">
              {NUTRIENT_ROWS.map(({ key, label, unit }) => {
                const value = exp.totals[key];
                const isUnknown = value === null || value === undefined || unknown.has(key);
                return (
                  <tr key={key}>
                    <th scope="row" className="px-3.5 py-2.5 text-left font-normal text-muted-foreground">
                      {label}
                    </th>
                    <td className="px-3.5 py-2.5 text-right font-semibold tabular-nums">
                      {isUnknown ? <span className="font-normal italic text-subtle-foreground">unknown</span> : nutrient(value, unit)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted-foreground">
            Amounts are planned from validated recipe data; Savora does not track what you eat.
          </p>
        </section>

        <section aria-labelledby="meal-why">
          <h3 id="meal-why" className="mb-2 text-sm font-semibold text-muted-foreground">
            Why this meal
          </h3>
          <div className="flex flex-col gap-2.5">
            {reasonsByKind(exp.reasons).map(([kind, reasons]) => (
              <div key={kind} className="rounded-2xl bg-surface-muted p-3.5">
                <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {kind === "LIMITATION" ? <Info className="size-3.5" aria-hidden /> : <CircleCheck className="size-3.5 text-success" aria-hidden />}
                  {REASON_LABEL[kind]}
                </p>
                <ul className="mt-1.5 flex flex-col gap-1 text-sm leading-relaxed">
                  {reasons.map((r) => (
                    <li key={`${r.code}-${r.message}`}>{r.message}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>

        <SafetyNotice safety={safety} />
      </div>
    </Sheet>
  );
}
