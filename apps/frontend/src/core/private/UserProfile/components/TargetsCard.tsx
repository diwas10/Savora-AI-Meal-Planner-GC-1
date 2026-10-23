import type { Schema } from "@savora/contracts";
import { Flame, Info } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { relativeTime } from "@/lib/format";
import { explainTargets, MACRO_SHARE } from "../lib/target-breakdown";

type NutritionTargets = Schema<"NutritionTargets">;
type Profile = Schema<"UserProfileDto">;

const MACRO_LABEL: Record<string, string> = {
  protein_g: "Protein",
  carbohydrate_g: "Carbohydrate",
  fat_g: "Fat",
};

const MEAL_LABEL: Record<string, string> = { BREAKFAST: "Breakfast", LUNCH: "Lunch", DINNER: "Dinner" };

const METHOD_LABEL: Record<string, string> = { MIFFLIN_ST_JEOR: "Mifflin-St Jeor" };

const num = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });
const fmt = (v: number | null | undefined) => (v === null || v === undefined ? "–" : num.format(v));
const pct = (v: number) => `${Math.round(v * 100)}%`;

/**
 * Versioned daily targets; clearly estimates for planning, not a clinical prescription.
 * With the profile it also shows the arithmetic, when that reproduces the stored target.
 */
export function TargetsCard({
  targets,
  profileVersion,
  profile,
}: {
  targets: NutritionTargets;
  profileVersion: number;
  profile?: Profile;
}) {
  const how = explainTargets(targets, profile);
  const energy = targets.energyKcal.target ?? 0;
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

      <div className="border-b border-border">
        <p className="px-5 pt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Daily nutrient ranges</p>
        <div className="grid grid-cols-3 divide-x divide-border pb-1 pt-2">
          {(targets.nutrientBounds ?? []).map((b) => {
            const share = MACRO_SHARE[b.nutrient];
            return (
              <div key={b.nutrient} className="px-2 py-3 text-center">
                <p className="text-xs font-medium text-muted-foreground">{MACRO_LABEL[b.nutrient] ?? b.nutrient}</p>
                <p className="mt-0.5 text-lg font-semibold tabular-nums leading-tight">
                  {fmt(b.bounds.min)}–{fmt(b.bounds.max)}
                  <span className="ml-0.5 text-xs font-normal text-muted-foreground">g</span>
                </p>
                {share && (
                  <p className="mt-0.5 text-[11px] text-muted-foreground tabular-nums">
                    {pct(share.low)}–{pct(share.high)} of energy
                  </p>
                )}
                {b.nutrient === "protein_g" && b.bounds.target != null && (
                  <p className="mt-1 text-[11px] font-medium text-primary tabular-nums">aim for ≥ {fmt(b.bounds.target)} g</p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {(targets.mealEnergyPolicy ?? []).length > 0 && (
        <div className="border-b border-border px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Energy per meal</p>
          <dl className="mt-2 grid grid-cols-[auto_1fr_auto] items-baseline gap-x-3 gap-y-1 text-sm">
            {(targets.mealEnergyPolicy ?? []).map((m) => (
              <div key={m.mealType} className="contents">
                <dt className="font-medium">{MEAL_LABEL[m.mealType] ?? m.mealType}</dt>
                <dd className="text-xs text-muted-foreground tabular-nums">
                  {pct(m.minFraction)}–{pct(m.maxFraction)} of the day
                </dd>
                <dd className="text-right font-semibold tabular-nums">
                  {fmt(energy * m.minFraction)}–{fmt(energy * m.maxFraction)} <span className="text-xs font-normal text-muted-foreground">kcal</span>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <div className="flex flex-col gap-3 p-5 text-sm">
        <p className="flex gap-2 text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          Estimates for meal planning, not a clinical prescription. Recalculated only when your
          body, activity or goal changes.
        </p>

        {how && (
          <details className="group rounded-2xl bg-surface-muted p-3 text-xs" open>
            <summary className="cursor-pointer text-sm font-semibold text-foreground">How these were calculated</summary>
            <ol className="mt-3 flex flex-col gap-3 text-muted-foreground">
              <Step n={1} title="Resting energy (Mifflin-St Jeor)">
                10 × {how.inputs.weightKg} kg + 6.25 × {how.inputs.heightCm} cm − 5 × {how.inputs.ageYears} yr{" "}
                {how.inputs.sexConstant < 0 ? "−" : "+"} {Math.abs(how.inputs.sexConstant)} ={" "}
                <Strong>{fmt(how.resting)} kcal</Strong>
              </Step>
              <Step n={2} title="Activity">
                {fmt(how.resting)} × {how.activityFactor} = <Strong>{fmt(how.maintenance)} kcal</Strong> to maintain weight
              </Step>
              <Step n={3} title="Goal">
                {fmt(how.maintenance)} × {how.goalFactor} = <Strong>{fmt(how.target)} kcal</Strong> target, with a planning range of
                ±{pct(how.band / how.target)} ({fmt(how.target - how.band)}–{fmt(how.target + how.band)})
              </Step>
              <Step n={4} title="Protein, carbohydrate and fat">
                Grams come from a share of {fmt(how.target)} kcal: protein 10–35% ÷ 4 kcal/g, carbohydrate 45–65% ÷ 4 kcal/g, fat
                20–35% ÷ 9 kcal/g. Protein is never lower than 0.8 g per kg of body weight (
                {how.proteinFloor.rda} g for you
                {how.proteinFloor.usesRda
                  ? `, which is above the ${how.proteinFloor.amdrMin} g that 10% gives, so ${how.proteinFloor.rda} g is the floor`
                  : `; 10% gives ${how.proteinFloor.amdrMin} g, which is higher, so that is the floor`}
                ).
              </Step>
            </ol>
          </details>
        )}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
          <dt>Method</dt>
          <dd className="text-right font-medium text-foreground">{METHOD_LABEL[targets.method] ?? targets.method.replaceAll("_", " ")}</dd>
          {targets.bmi != null && (
            <>
              <dt>BMI (information only)</dt>
              <dd className="text-right font-medium text-foreground tabular-nums">{targets.bmi.toFixed(1)}</dd>
            </>
          )}
          <dt>Profile version</dt>
          <dd className="text-right font-medium text-foreground tabular-nums">v{profileVersion}</dd>
          <dt>Formula</dt>
          <dd className="text-right font-medium text-foreground">{targets.formulaVersion}</dd>
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

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-2.5">
      <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-pill bg-primary-soft text-[11px] font-semibold text-primary-soft-foreground">
        {n}
      </span>
      <div className="min-w-0">
        <p className="font-semibold text-foreground">{title}</p>
        <p className="mt-0.5 leading-relaxed tabular-nums">{children}</p>
      </div>
    </li>
  );
}

function Strong({ children }: { children: React.ReactNode }) {
  return <span className="font-semibold text-foreground">{children}</span>;
}
