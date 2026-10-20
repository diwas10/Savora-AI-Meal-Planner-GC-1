"use client";

import Link from "next/link";
import { OnboardingWizard } from "./OnboardingWizard";
import { useProfileQuery } from "../service/profile.query";

function formatBound(bound?: {
  min?: number | null;
  target?: number | null;
  max?: number | null;
}) {
  if (!bound) return "unknown";
  const parts: string[] = [];
  if (bound.target != null) parts.push(`${Math.round(bound.target)}`);
  if (bound.min != null || bound.max != null) {
    parts.push(`(${bound.min ?? "–"} to ${bound.max ?? "–"})`);
  }
  return parts.length > 0 ? parts.join(" ") : "unknown";
}

export function ProfileSummaryView() {
  const profileQuery = useProfileQuery();

  if (profileQuery.isLoading) {
    return <p className="text-sm text-neutral-600">Loading profile & targets...</p>;
  }

  const data = profileQuery.data;
  const nutrientBounds = data?.targets.nutrientBounds ?? [];

  return (
    <div className="space-y-8">
      {data && (
        <section className="mx-auto max-w-3xl rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-bold text-neutral-900">
                Active Nutrition Targets (Profile v{data.profile.version})
              </h2>
              <p className="text-xs text-neutral-500">
                Method: {data.targets.method} · Formula: {data.targets.formulaVersion}
                {data.targets.bmi != null ? ` · BMI: ${data.targets.bmi.toFixed(1)}` : ""}
              </p>
            </div>
            {data.needsSeedPicks && (
              <Link
                href="/onboarding"
                className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700"
              >
                Pick 3–5 Seed Dishes Required
              </Link>
            )}
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-neutral-50 p-3">
              <div className="text-xs text-neutral-500">Daily Energy (kcal)</div>
              <div className="mt-1 text-lg font-bold text-neutral-900">
                {formatBound(data.targets.energyKcal)}
              </div>
            </div>
            {nutrientBounds.map((nb) => (
              <div key={nb.nutrient} className="rounded-lg bg-neutral-50 p-3">
                <div className="text-xs text-neutral-500">{nb.nutrient}</div>
                <div className="mt-1 text-lg font-bold text-neutral-900">
                  {formatBound(nb.bounds)}
                </div>
              </div>
            ))}
            <div className="rounded-lg bg-neutral-50 p-3">
              <div className="text-xs text-neutral-500">Seed Recipes Stored</div>
              <div className="mt-1 text-sm font-semibold text-neutral-900">
                {data.profile.seedRecipeIds.length} picks
              </div>
            </div>
          </div>

          {data.targets.provenance && data.targets.provenance.length > 0 && (
            <div className="mt-4 border-t border-neutral-100 pt-3 text-xs text-neutral-500">
              Provenance: {data.targets.provenance.join(" · ")}
            </div>
          )}
        </section>
      )}

      <OnboardingWizard />
    </div>
  );
}
