import type { Schema } from "@savora/contracts";
import { Flame, Info } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { relativeTime } from "@/lib/format";

type NutritionTargets = Schema<"NutritionTargets">;

const MACRO_LABEL: Record<string, string> = {
  protein_g: "Protein",
  carbohydrate_g: "Carbohydrate",
  fat_g: "Fat",
};

const fmt = (v: number | null | undefined) =>
  v === null || v === undefined ? "–" : new Intl.NumberFormat("en", { maximumFractionDigits: 0 }).format(v);

/** Versioned daily targets; clearly estimates for planning, not a clinical prescription. */
export function TargetsCard({ targets, profileVersion }: { targets: NutritionTargets; profileVersion: number }) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="bg-gradient-to-br from-hero-from via-hero-via to-hero-to p-5 text-hero-ink">
        <p className="flex items-center gap-1.5 text-sm font-medium opacity-90">
          <Flame className="size-4" aria-hidden /> Estimated daily energy
        </p>
        <p className="mt-1 text-4xl font-bold tabular-nums tracking-tight">
          {fmt(targets.energyKcal.target)} <span className="text-lg font-semibold opacity-80">kcal</span>
        </p>
        <p className="text-sm opacity-90">
          planning range {fmt(targets.energyKcal.min)}–{fmt(targets.energyKcal.max)} kcal
        </p>
      </div>
      <div className="grid grid-cols-3 divide-x divide-border border-b border-border">
        {(targets.nutrientBounds ?? []).map((b) => (
          <div key={b.nutrient} className="p-3.5 text-center">
            <p className="text-xs font-medium text-muted-foreground">{MACRO_LABEL[b.nutrient] ?? b.nutrient}</p>
            <p className="mt-0.5 font-semibold tabular-nums">
              {fmt(b.bounds.min)}–{fmt(b.bounds.max)}
              <span className="text-xs font-normal text-muted-foreground"> g</span>
            </p>
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-3 p-5 text-sm">
        <p className="flex gap-2 text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          Estimates for meal planning, not a clinical prescription. Recalculated only when your
          body, activity or goal changes.
        </p>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <dt>Method</dt>
          <dd className="text-right font-medium text-foreground">{targets.method.replaceAll("_", "-").toLowerCase()}</dd>
          {targets.bmi != null && (
            <>
              <dt>BMI (information only)</dt>
              <dd className="text-right font-medium text-foreground">{targets.bmi.toFixed(1)}</dd>
            </>
          )}
          <dt>Profile version</dt>
          <dd className="text-right font-medium text-foreground">v{profileVersion} · {targets.formulaVersion}</dd>
          <dt>Calculated</dt>
          <dd className="text-right font-medium text-foreground">{relativeTime(targets.calculatedAt)}</dd>
        </dl>
        {targets.provenance && targets.provenance.length > 0 && (
          <details className="group rounded-2xl bg-surface-muted p-3 text-xs">
            <summary className="cursor-pointer font-semibold text-foreground">Sources and assumptions</summary>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-muted-foreground">
              {targets.provenance.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </Card>
  );
}
