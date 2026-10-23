"use client";

import type { Schema } from "@savora/contracts";
import { ChefHat, CircleCheck, Info, Utensils } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { InlineAlert } from "@/components/ui/States";
import { Sheet } from "@/components/ui/Sheet";
import { NUTRIENT_ROWS, dishName, nutrient } from "@/lib/format";
import { REASON_LABEL, cookWithout, reasonsByKind } from "@/core/private/MealPlanning/lib/meal";

type CravingItem = Schema<"CravingItem">;

export function RecipeSheet({
  item,
  open,
  onOpenChange,
}: {
  item: CravingItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!item) return null;
  const name = dishName(item.name);
  const exp = item.explanation;
  const ingredients = exp.ingredients ?? [];
  const steps = exp.steps ?? [];

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={name.title} description={name.subtitle ?? item.cuisines.join(" · ")}>
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="accent">#{item.rank} for you</Badge>
          {item.cuisines.map((c) => (
            <Badge key={c}>{c}</Badge>
          ))}
        </div>

        {cookWithout(exp.reasons) && (
          <InlineAlert tone="warning" title="Cook it your way">
            {cookWithout(exp.reasons)}
          </InlineAlert>
        )}

        {/* Ingredients section */}
        {ingredients.length > 0 && (
          <section aria-labelledby="recipe-ingredients">
            <h3 id="recipe-ingredients" className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
              <Utensils className="size-4 text-primary" aria-hidden />
              Ingredients ({ingredients.length})
            </h3>
            <ul className="grid grid-cols-1 gap-2 rounded-2xl bg-surface p-4 ring-1 ring-border sm:grid-cols-2 text-sm">
              {ingredients.map((ingr, i) => (
                <li key={i} className="flex items-center gap-2 text-foreground">
                  <span className="size-1.5 shrink-0 rounded-full bg-primary" />
                  <span className="capitalize">{ingr}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Recipe preparation steps */}
        {steps.length > 0 && (
          <section aria-labelledby="recipe-steps">
            <h3 id="recipe-steps" className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
              <ChefHat className="size-4 text-primary" aria-hidden />
              Recipe & Instructions ({steps.length} {steps.length === 1 ? "step" : "steps"})
            </h3>
            <ol className="flex flex-col gap-3 rounded-2xl bg-surface p-4 ring-1 ring-border text-sm">
              {steps.map((step, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-surface-muted text-xs font-semibold text-muted-foreground ring-1 ring-border">
                    {idx + 1}
                  </span>
                  <p className="leading-relaxed text-foreground">{step}</p>
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* Full Nutrition Label */}
        <section aria-labelledby="recipe-nutrients">
          <h3 id="recipe-nutrients" className="mb-2 text-sm font-semibold text-muted-foreground">
            Planned nutrition (Standard portion: {exp.standardPortion})
          </h3>
          <table className="w-full overflow-hidden rounded-2xl bg-surface text-sm ring-1 ring-border">
            <caption className="sr-only">Nutrients for one standard portion</caption>
            <tbody className="divide-y divide-border">
              {NUTRIENT_ROWS.map(({ key, label, unit }) => (
                <tr key={key}>
                  <th scope="row" className="px-3.5 py-2.5 text-left font-normal text-muted-foreground">
                    {label}
                  </th>
                  <td className="px-3.5 py-2.5 text-right font-semibold tabular-nums">
                    {exp.standardNutrients[key] == null ? (
                      <span className="font-normal italic text-subtle-foreground">unknown</span>
                    ) : (
                      nutrient(exp.standardNutrients[key], unit)
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <InlineAlert tone="info" icon={<Info className="size-4" aria-hidden />}>
          Not checked against today&apos;s remaining targets.
        </InlineAlert>

        <section aria-labelledby="recipe-why">
          <h3 id="recipe-why" className="mb-2 text-sm font-semibold text-muted-foreground">
            Why it&apos;s suggested
          </h3>
          <div className="flex flex-col gap-2.5">
            {reasonsByKind(exp.reasons).map(([kind, reasons]) => (
              <div key={kind} className="rounded-2xl bg-surface-muted p-3.5">
                <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <CircleCheck className="size-3.5 text-success" aria-hidden />
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
      </div>
    </Sheet>
  );
}
