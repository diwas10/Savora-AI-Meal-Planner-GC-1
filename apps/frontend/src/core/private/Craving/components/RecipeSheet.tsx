"use client";

import type { Schema } from "@savora/contracts";
import { CircleCheck, Info } from "lucide-react";
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
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={name.title} description={name.subtitle ?? item.cuisines.join(" · ")}>
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="accent">#{item.rank} for you</Badge>
          {item.cuisines.map((c) => (
            <Badge key={c}>{c}</Badge>
          ))}
        </div>
        <section aria-labelledby="recipe-nutrients">
          <h3 id="recipe-nutrients" className="mb-2 text-sm font-semibold text-muted-foreground">
            Standard portion: {exp.standardPortion}
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
        {cookWithout(exp.reasons) && (
          <InlineAlert tone="warning" title="Cook it your way">
            {cookWithout(exp.reasons)}
          </InlineAlert>
        )}
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
