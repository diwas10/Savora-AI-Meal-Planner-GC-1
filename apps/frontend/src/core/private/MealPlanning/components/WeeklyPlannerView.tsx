"use client";

import type { Schema } from "@savora/contracts";
import { useState } from "react";
import { SafetyNotice } from "@/components/ui/SafetyNotice";
import {
  useCreateMealPlanMutation,
  useCreateSubstitutionMutation,
  useMealPlanDetailQuery,
  useMealPlansListQuery,
  useSubstitutionPollingQuery,
} from "../service/meal-planning.query";

type PlannedMeal = Schema<"PlannedMeal">;

function formatNutrient(val?: number | null, unit = ""): string {
  if (val === null || val === undefined) {
    return "unknown";
  }
  return `${Math.round(val)}${unit ? ` ${unit}` : ""}`;
}

export function WeeklyPlannerView({
  initialSwapSlot,
}: {
  initialSwapSlot?: string | null;
}) {
  const currentListQuery = useMealPlansListQuery(true);
  const allPlansQuery = useMealPlansListQuery(false);

  const [activePlanId, setActivePlanId] = useState<string | null>(null);
  const [activeSubId, setActiveSubId] = useState<string | null>(null);
  const [selectedMealForExplain, setSelectedMealForExplain] =
    useState<PlannedMeal | null>(null);
  const [weekStartInput, setWeekStartInput] = useState("2026-10-26");

  const subPollingQuery = useSubstitutionPollingQuery(activeSubId);
  const swappedPlanId =
    subPollingQuery.data?.status === "FEASIBLE"
      ? (subPollingQuery.data.toPlanId ?? null)
      : null;

  const currentPlanId =
    swappedPlanId ??
    activePlanId ??
    currentListQuery.data?.[0]?.id ??
    allPlansQuery.data?.[0]?.id ??
    null;

  const detailQuery = useMealPlanDetailQuery(currentPlanId);
  const createPlanMutation = useCreateMealPlanMutation();
  const createSubMutation = useCreateSubstitutionMutation(currentPlanId ?? "");

  const handleGenerateWeek = async () => {
    setActiveSubId(null);
    const res = await createPlanMutation.mutateAsync({ weekStart: weekStartInput });
    setActivePlanId(res.planId);
  };

  const handleSwapSlot = async (slotId: string, revision: number) => {
    if (!currentPlanId) return;
    const res = await createSubMutation.mutateAsync({
      slotId,
      expectedRevision: revision,
      excludeCombinationIds: [],
    });
    setActiveSubId(res.substitutionId);
  };

  const plan = detailQuery.data;
  const planSlots = plan?.slots ?? [];
  const planDayTotals = plan?.dayTotals ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-neutral-200 bg-white p-5 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Weekly Meal Planner</h1>
          <p className="mt-1 text-sm text-neutral-600">
            21-slot weekly schedule verified by the weekly CSP solver.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <input
            type="date"
            value={weekStartInput}
            onChange={(e) => setWeekStartInput(e.target.value)}
            aria-label="Week start date"
            className="rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          />
          <button
            type="button"
            disabled={
              createPlanMutation.isPending || plan?.status === "GENERATING"
            }
            onClick={handleGenerateWeek}
            className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
          >
            {plan?.status === "GENERATING"
              ? "Generating Week..."
              : "Generate Week"}
          </button>
        </div>
      </div>

      {createPlanMutation.error instanceof Error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800">
          {createPlanMutation.error.message}
        </div>
      )}

      {createSubMutation.error instanceof Error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800">
          {createSubMutation.error.message}
        </div>
      )}

      {initialSwapSlot && plan && plan.status === "FEASIBLE" && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-950">
          <span>
            Swap requested from Craving chat for slot <strong>{initialSwapSlot}</strong>.
          </span>
          <button
            type="button"
            onClick={() => handleSwapSlot(initialSwapSlot, plan.revision)}
            className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-800"
          >
            Confirm Swap for {initialSwapSlot}
          </button>
        </div>
      )}

      {subPollingQuery.data && subPollingQuery.data.status === "GENERATING" && (
        <div className="rounded-lg border border-blue-300 bg-blue-50 p-4 text-sm text-blue-900">
          Swapping slot <strong>{subPollingQuery.data.slotId}</strong> (locking the other 20
          slots in the weekly CSP)... Polling status every 2 seconds.
        </div>
      )}

      {plan && (
        <>
          <SafetyNotice safety={plan.safety} />

          <div className="flex flex-wrap items-center gap-3 text-xs text-neutral-600">
            <span className="rounded bg-neutral-100 px-2.5 py-1 font-medium text-neutral-800">
              Status: {plan.status}
            </span>
            <span className="rounded bg-neutral-100 px-2.5 py-1 font-medium text-neutral-800">
              Revision: r{plan.revision}
            </span>
            <span className="rounded bg-neutral-100 px-2.5 py-1">
              Profile v{plan.profileVersion}
            </span>
            {plan.fallbackReason === "MODEL_UNAVAILABLE" && (
              <span className="rounded-full bg-amber-100 px-3 py-1 font-semibold text-amber-900">
                Ranked by popularity
              </span>
            )}
            {plan.kbId && (
              <span className="rounded bg-neutral-100 px-2.5 py-1">
                KB: {plan.kbId} ({plan.kbVersion})
              </span>
            )}
          </div>

          {plan.status === "GENERATING" && (
            <div className="rounded-xl border border-blue-200 bg-blue-50 p-6 text-sm text-blue-950">
              <div className="font-semibold">
                Weekly CSP solver is running in the background...
              </div>
              <p className="mt-1">
                {plan.message ??
                  "Verifying 21 slots against dietary and repetition rules. This page polls automatically."}
              </p>
            </div>
          )}

          {(plan.status === "INFEASIBLE" ||
            plan.status === "INSUFFICIENT_DATA" ||
            plan.status === "TIMEOUT" ||
            plan.status === "FAILED") && (
            <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-900">
              <div className="font-bold">Plan Outcome: {plan.status}</div>
              <p className="mt-1">{plan.message}</p>
            </div>
          )}

          {plan.status === "FEASIBLE" && (
            <div className="space-y-6">
              {[1, 2, 3, 4, 5, 6, 7].map((dayIndex) => {
                const daySlots = planSlots.filter((s) => s.dayIndex === dayIndex);
                const dayTotal = planDayTotals.find((d) => d.dayIndex === dayIndex);
                const calDate = daySlots[0]?.calendarDate ?? `Day ${dayIndex}`;

                return (
                  <div
                    key={dayIndex}
                    className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-neutral-100 pb-3">
                      <h2 className="text-base font-bold text-neutral-900">
                        Day {dayIndex} · {calDate}
                      </h2>
                      {dayTotal && (
                        <div className="flex flex-wrap gap-3 text-xs text-neutral-700">
                          <span>
                            Energy:{" "}
                            <strong>
                              {formatNutrient(dayTotal.totals.energyKcal, "kcal")}
                            </strong>
                          </span>
                          <span>
                            Protein:{" "}
                            <strong>
                              {formatNutrient(dayTotal.totals.proteinG, "g")}
                            </strong>
                          </span>
                          <span>
                            Carbs:{" "}
                            <strong>
                              {formatNutrient(dayTotal.totals.carbohydrateG, "g")}
                            </strong>
                          </span>
                          <span>
                            Fat:{" "}
                            <strong>
                              {formatNutrient(dayTotal.totals.fatG, "g")}
                            </strong>
                          </span>
                          <span>
                            Sodium:{" "}
                            <strong>
                              {formatNutrient(dayTotal.totals.sodiumMg, "mg")}
                            </strong>
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-3">
                      {daySlots.map((slot) => {
                        const meal = slot.snapshot;
                        const exp = meal.explanation;
                        return (
                          <div
                            key={slot.slotId}
                            className="flex flex-col justify-between rounded-lg border border-neutral-200 p-4"
                          >
                            <div>
                              <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-emerald-800">
                                <span>{slot.mealType}</span>
                                <span className="text-neutral-500">{slot.preset}</span>
                              </div>
                              <ul className="mt-2 space-y-1 text-sm font-medium text-neutral-900">
                                {exp.dishes.map((d) => (
                                  <li key={d.dishId}>
                                    {d.name}{" "}
                                    <span className="text-xs font-normal text-neutral-500">
                                      ({d.portion})
                                    </span>
                                  </li>
                                ))}
                              </ul>
                              <div className="mt-2 text-xs text-neutral-600">
                                {formatNutrient(exp.totals.energyKcal, "kcal")} · Protein{" "}
                                {formatNutrient(exp.totals.proteinG, "g")} · Sodium{" "}
                                {formatNutrient(exp.totals.sodiumMg, "mg")}
                              </div>
                            </div>

                            <div className="mt-4 flex items-center justify-between border-t border-neutral-100 pt-3">
                              <button
                                type="button"
                                onClick={() => setSelectedMealForExplain(meal)}
                                className="text-xs font-medium text-emerald-700 hover:underline"
                              >
                                Explain Meal
                              </button>
                              <button
                                type="button"
                                disabled={
                                  !plan.isCurrent ||
                                  createSubMutation.isPending ||
                                  subPollingQuery.data?.status === "GENERATING"
                                }
                                onClick={() => handleSwapSlot(slot.slotId, plan.revision)}
                                className="rounded border border-neutral-300 px-2.5 py-1 text-xs font-semibold text-neutral-800 hover:bg-neutral-100 disabled:opacity-50"
                              >
                                Swap
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {selectedMealForExplain && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Meal explanation drawer"
          className="fixed inset-0 z-50 flex items-center justify-end bg-black/40"
        >
          <div className="h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-neutral-200 pb-3">
              <h3 className="text-lg font-bold text-neutral-900">
                Explanation · {selectedMealForExplain.slotId}
              </h3>
              <button
                type="button"
                onClick={() => setSelectedMealForExplain(null)}
                className="rounded px-2 py-1 text-sm font-semibold text-neutral-600 hover:bg-neutral-100"
              >
                Close
              </button>
            </div>

            <div className="mt-4 space-y-4 text-sm">
              <div>
                <h4 className="font-semibold text-neutral-800">Dishes & Portions</h4>
                <ul className="mt-1 space-y-1 text-neutral-700">
                  {selectedMealForExplain.explanation.dishes.map((d) => (
                    <li key={d.dishId}>
                      {d.name} — {d.portion} ({d.role})
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="font-semibold text-neutral-800">Reasons & Provenance</h4>
                <ul className="mt-1 space-y-2">
                  {selectedMealForExplain.explanation.reasons.map((r, idx) => (
                    <li
                      key={`${r.code}-${idx}`}
                      className="rounded border border-neutral-200 bg-neutral-50 p-2.5"
                    >
                      <div className="text-xs font-bold text-emerald-800">
                        [{r.kind}] {r.code}
                      </div>
                      <div className="mt-0.5 text-xs text-neutral-700">{r.message}</div>
                    </li>
                  ))}
                </ul>
              </div>

              {selectedMealForExplain.explanation.unknownNutrients.length > 0 && (
                <div className="rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  Unknown nutrients:{" "}
                  {selectedMealForExplain.explanation.unknownNutrients.join(", ")}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
