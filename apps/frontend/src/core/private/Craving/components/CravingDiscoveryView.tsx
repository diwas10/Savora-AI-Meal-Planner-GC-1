"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { SafetyNotice } from "@/components/ui/SafetyNotice";
import { cravingFormSchema, type CravingFormValues } from "../schema/craving.schema";
import { useCravingMutation } from "../service/craving.query";

function formatNutrient(val?: number | null, unit = ""): string {
  if (val === null || val === undefined) {
    return "unknown";
  }
  return `${Math.round(val)}${unit ? ` ${unit}` : ""}`;
}

export function CravingDiscoveryView() {
  const cravingMutation = useCravingMutation();
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<CravingFormValues>({
    resolver: zodResolver(cravingFormSchema),
    defaultValues: { text: "" },
  });

  const onSubmit = async (values: CravingFormValues) => {
    await cravingMutation.mutateAsync(values);
  };

  const data = cravingMutation.data;
  const parsedRequest =
    data === undefined
      ? undefined
      : "result" in data
        ? data.result.request
        : data.request;

  const chips: string[] = [];
  if (parsedRequest) {
    for (const c of parsedRequest.cuisineIds ?? []) {
      chips.push(c);
    }
    for (const f of parsedRequest.flavorTags ?? []) {
      chips.push(f.toLowerCase());
    }
    for (const ex of parsedRequest.excludedIngredientIds ?? []) {
      chips.push(`no ${ex.toLowerCase().replace(/_/g, " ")}`);
    }
    if (parsedRequest.mealSlotId) {
      chips.push(`slot: ${parsedRequest.mealSlotId}`);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-neutral-900">
          Craving Discovery & Meal Swap Assistant
        </h1>
        <p className="mt-1 text-sm text-neutral-600">
          Ask in natural language (e.g., &ldquo;something spicy Chinese without noodles&rdquo; or
          &ldquo;swap Tuesday lunch for something lighter&rdquo;).
        </p>

        <form onSubmit={handleSubmit(onSubmit)} className="mt-4 space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              type="text"
              placeholder="What are you craving right now?"
              {...register("text")}
              className="flex-1 rounded-lg border border-neutral-300 px-4 py-2.5 text-sm focus:border-emerald-600 focus:outline-none"
            />
            <button
              type="submit"
              disabled={cravingMutation.isPending}
              className="rounded-lg bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
            >
              {cravingMutation.isPending ? "Analyzing..." : "Find Dishes"}
            </button>
          </div>
          {errors.text && (
            <p className="text-xs text-red-600">{errors.text.message}</p>
          )}
        </form>

        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="text-neutral-500">Examples:</span>
          {[
            "something spicy Chinese without noodles",
            "creamy Indian curry without mushrooms",
            "swap Tuesday lunch for something Thai",
          ].map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setValue("text", example, { shouldValidate: true })}
              className="rounded-full border border-neutral-200 bg-neutral-50 px-2.5 py-0.5 text-neutral-700 hover:bg-neutral-100"
            >
              {example}
            </button>
          ))}
        </div>
      </div>

      {cravingMutation.error instanceof Error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800">
          {cravingMutation.error.message}
        </div>
      )}

      {data && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-neutral-200 bg-white p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
                Parsed Intent ({data.parse.parser}):
              </span>
              <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-900">
                {parsedRequest?.intent}
              </span>
              {chips.length > 0 && (
                <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-800">
                  {chips.join(" · ")}
                </span>
              )}
            </div>
            <span className="text-xs font-medium text-amber-800">
              Not checked against today&apos;s remaining targets
            </span>
          </div>

          {!("result" in data) && (
            <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-5 text-sm text-emerald-950">
              <h2 className="text-base font-bold">Planned Meal Swap Detected</h2>
              {data.request.mealSlotId ? (
                <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
                  <p>
                    Ready to swap slot <strong>{data.request.mealSlotId}</strong> on your
                    weekly plan while keeping the other 20 slots locked.
                  </p>
                  <Link
                    href={`/dashboard?swapSlot=${encodeURIComponent(data.request.mealSlotId)}`}
                    className="rounded-lg bg-emerald-700 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-800"
                  >
                    Swap {data.request.mealSlotId} on Weekly Plan
                  </Link>
                </div>
              ) : (
                <p className="mt-1">
                  {data.clarification ??
                    "Please specify which day and meal (e.g., 'swap Tuesday lunch') you want to replace."}
                </p>
              )}
            </div>
          )}

          {"result" in data && (
            <>
              <SafetyNotice safety={data.result.safety} />

              {data.result.fallbackReason === "MODEL_UNAVAILABLE" && (
                <div className="inline-block rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-900">
                  Ranked by popularity
                </div>
              )}

              {data.result.status === "NEEDS_CLARIFICATION" && (
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-950">
                  <div className="font-bold">Clarification Needed</div>
                  <p className="mt-1">
                    {data.parse.clarification ??
                      "Could you clarify the cuisine, flavor profile, or dish style you are looking for?"}
                  </p>
                </div>
              )}

              {data.result.status === "NO_MATCH" && (
                <div className="rounded-xl border border-neutral-300 bg-white p-5 text-sm text-neutral-800">
                  <div className="font-bold">No Matching Dishes Found</div>
                  <p className="mt-1">
                    No dishes matched all of your active filters and profile rules.
                  </p>
                  {data.result.unknownCuisineIds.length > 0 && (
                    <p className="mt-1 text-xs text-red-700">
                      Unknown cuisine(s): {data.result.unknownCuisineIds.join(", ")}. Try a
                      catalogue cuisine such as Nepali, Indian, Chinese, Thai, or Italian.
                    </p>
                  )}
                  {data.result.unmatchedFlavorTags.length > 0 && (
                    <p className="mt-1 text-xs text-amber-800">
                      Unmatched flavor tag(s):{" "}
                      {data.result.unmatchedFlavorTags.join(", ")}. Try relaxing the flavor
                      tag or ingredient exclusions.
                    </p>
                  )}
                </div>
              )}

              {data.result.status === "OK" && (
                <div className="grid gap-4 md:grid-cols-2">
                  {data.result.items.map((item) => {
                    const exp = item.explanation;
                    return (
                      <div
                        key={item.recipeId}
                        className="flex flex-col justify-between rounded-xl border border-neutral-200 bg-white p-5 shadow-sm"
                      >
                        <div>
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-900">
                                #{item.rank}
                              </span>
                              <h3 className="mt-1 text-base font-bold text-neutral-900">
                                {item.name}
                              </h3>
                            </div>
                            <span className="text-xs text-neutral-500">
                              {item.cuisines.join(" · ")}
                            </span>
                          </div>

                          <div className="mt-2 text-xs text-neutral-700">
                            Standard Portion: <strong>{exp.standardPortion}</strong>
                          </div>

                          <div className="mt-2 flex flex-wrap gap-3 text-xs text-neutral-700">
                            <span>
                              Energy:{" "}
                              <strong>
                                {formatNutrient(exp.standardNutrients.energyKcal, "kcal")}
                              </strong>
                            </span>
                            <span>
                              Protein:{" "}
                              <strong>
                                {formatNutrient(exp.standardNutrients.proteinG, "g")}
                              </strong>
                            </span>
                            <span>
                              Carbs:{" "}
                              <strong>
                                {formatNutrient(
                                  exp.standardNutrients.carbohydrateG,
                                  "g",
                                )}
                              </strong>
                            </span>
                            <span>
                              Fat:{" "}
                              <strong>
                                {formatNutrient(exp.standardNutrients.fatG, "g")}
                              </strong>
                            </span>
                            <span>
                              Sodium:{" "}
                              <strong>
                                {formatNutrient(exp.standardNutrients.sodiumMg, "mg")}
                              </strong>
                            </span>
                          </div>

                          <div className="mt-3 space-y-1 border-t border-neutral-100 pt-2">
                            {exp.reasons.map((r, i) => (
                              <div
                                key={`${r.code}-${i}`}
                                className="text-xs text-neutral-600"
                              >
                                <span className="font-semibold text-neutral-800">
                                  [{r.kind}]
                                </span>{" "}
                                {r.message}
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="mt-3 border-t border-neutral-100 pt-2 text-[11px] font-medium text-amber-900">
                          Not checked against today&apos;s remaining targets
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
