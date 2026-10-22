import type { Schema } from "@savora/contracts";
import { Card } from "@/components/ui/Card";
import { RangeBar } from "@/components/ui/RangeBar";

type NutrientVector = Schema<"NutrientVector">;
type NutritionTargets = Schema<"NutritionTargets">;

function bounds(targets: NutritionTargets | undefined, nutrient: string) {
  return targets?.nutrientBounds?.find((b) => b.nutrient === nutrient)?.bounds;
}

/** Planned day totals against the estimated targets (never "consumed"). */
export function NutritionSummary({
  totals,
  targets,
  title = "Planned for this day",
}: {
  totals: NutrientVector | null | undefined;
  targets?: NutritionTargets;
  title?: string;
}) {
  const protein = bounds(targets, "protein_g");
  const carbs = bounds(targets, "carbohydrate_g");
  const fat = bounds(targets, "fat_g");
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
        <span className="text-xs text-muted-foreground">Estimated targets</span>
      </div>
      <div className="flex flex-col gap-4">
        <RangeBar label="Energy" unit="kcal" planned={totals?.energyKcal} min={targets?.energyKcal.min} max={targets?.energyKcal.max} />
        <div className="grid gap-4 sm:grid-cols-3">
          <RangeBar label="Protein" unit="g" planned={totals?.proteinG} min={protein?.min} max={protein?.max} />
          <RangeBar label="Carbohydrate" unit="g" planned={totals?.carbohydrateG} min={carbs?.min} max={carbs?.max} />
          <RangeBar label="Fat" unit="g" planned={totals?.fatG} min={fat?.min} max={fat?.max} />
        </div>
      </div>
      <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
        Portions are sized toward these estimates before the weekly check, which confirms
        every meal fits your rules. Reaching the estimates is not yet a verified rule.
      </p>
    </Card>
  );
}
