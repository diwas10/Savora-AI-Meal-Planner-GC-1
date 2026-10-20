"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { profileFormSchema, type ProfileFormValues } from "../schema/profile.schema";
import {
  useConfirmSeedPicksMutation,
  useCuisinesQuery,
  useDishSearchQuery,
  useProfileQuery,
  useSeedSuggestionsQuery,
  useUpsertProfileMutation,
} from "../service/profile.query";

const CLINICAL_CONDITIONS: Array<{
  id: "TYPE_2_DIABETES" | "HYPERTENSION" | "DYSLIPIDEMIA";
  label: string;
}> = [
  { id: "TYPE_2_DIABETES", label: "Type 2 Diabetes" },
  { id: "HYPERTENSION", label: "Hypertension" },
  { id: "DYSLIPIDEMIA", label: "Dyslipidemia" },
];

export function OnboardingWizard() {
  const router = useRouter();
  const profileQuery = useProfileQuery();
  const cuisinesQuery = useCuisinesQuery();
  const upsertProfileMutation = useUpsertProfileMutation();
  const confirmSeedsMutation = useConfirmSeedPicksMutation();

  const [step, setStep] = useState<"profile" | "seeds">("profile");
  const [selectedSeeds, setSelectedSeeds] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState("");

  const seedSuggestionsQuery = useSeedSuggestionsQuery(step === "seeds");
  const dishSearchQuery = useDishSearchQuery(searchTerm);

  const existing = profileQuery.data?.profile;
  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { errors },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    values: {
      ageYears: existing?.ageYears ?? 28,
      sex: existing?.sex ?? "FEMALE",
      heightCm: existing?.heightCm ?? 165,
      weightKg: existing?.weightKg ?? 62,
      activity: existing?.activity ?? "MODERATE",
      goal: existing?.goal ?? "MAINTAIN",
      diet: existing?.diet ?? "NONE",
      cuisinePolicy: existing?.cuisinePolicy ?? "MIXED",
      cuisines: existing?.cuisines ?? ["Nepali", "Indian"],
      excludedIngredientsText: existing?.excludedIngredients?.join(", ") ?? "",
      allergiesText: existing?.allergies?.join(", ") ?? "",
      allergiesConfirmed: Boolean(existing?.allergiesConfirmedAt),
      conditions: existing?.conditions ?? [],
    },
  });

  const watchedCuisines = useWatch({ control, name: "cuisines" }) ?? [];
  const watchedConditions = useWatch({ control, name: "conditions" }) ?? [];
  const watchedAllergiesText = useWatch({ control, name: "allergiesText" }) ?? "";

  const toggleCuisine = (name: string) => {
    const next = watchedCuisines.includes(name)
      ? watchedCuisines.filter((c) => c !== name)
      : [...watchedCuisines, name];
    setValue("cuisines", next, { shouldValidate: true });
  };

  const toggleCondition = (
    cond: "TYPE_2_DIABETES" | "HYPERTENSION" | "DYSLIPIDEMIA",
  ) => {
    const next = watchedConditions.includes(cond)
      ? watchedConditions.filter((c) => c !== cond)
      : [...watchedConditions, cond];
    setValue("conditions", next, { shouldValidate: true });
  };

  const onSaveProfile = async (values: ProfileFormValues) => {
    const excludedIngredients = values.excludedIngredientsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const allergies = values.allergiesText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const res = await upsertProfileMutation.mutateAsync({
      ageYears: values.ageYears,
      sex: values.sex,
      heightCm: values.heightCm,
      weightKg: values.weightKg,
      activity: values.activity,
      goal: values.goal,
      diet: values.diet === "NONE" ? null : values.diet,
      cuisinePolicy: values.cuisinePolicy,
      cuisines: values.cuisines,
      excludedIngredients,
      allergies,
      allergiesConfirmed: allergies.length > 0 ? values.allergiesConfirmed : false,
      conditions: values.conditions,
    });
    setSelectedSeeds(res.profile.seedRecipeIds ?? []);
    setStep("seeds");
  };

  const toggleSeedPick = (recipeId: string) => {
    setSelectedSeeds((prev) => {
      if (prev.includes(recipeId)) {
        return prev.filter((id) => id !== recipeId);
      }
      if (prev.length >= 5) {
        return prev;
      }
      return [...prev, recipeId];
    });
  };

  const onSaveSeeds = async () => {
    await confirmSeedsMutation.mutateAsync({ recipeIds: selectedSeeds });
    router.push("/dashboard");
  };

  if (step === "seeds") {
    const suggestions = seedSuggestionsQuery.data?.suggestions ?? [];
    const searchResults = dishSearchQuery.data ?? [];

    return (
      <div className="mx-auto max-w-4xl space-y-6 rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">
              Pick 3 to 5 Seed Dishes You Enjoy
            </h1>
            <p className="mt-1 text-sm text-neutral-600">
              These anchor the sequence recommendation model for your weekly plan and cravings.
            </p>
          </div>
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-900">
            Selected: {selectedSeeds.length} / 5 (minimum 3)
          </span>
        </div>

        <div
          role="note"
          className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-950"
        >
          Seed suggestions are screened against your diet and ingredient exclusions using the
          stand-in rule set ({seedSuggestionsQuery.data?.method ?? "popularity"}).
        </div>

        {confirmSeedsMutation.error instanceof Error && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">
            {confirmSeedsMutation.error.message}
          </div>
        )}

        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-700">
            Recommended Shortlist (12 Rule-Screened Dishes)
          </h2>
          {seedSuggestionsQuery.isLoading ? (
            <p className="mt-2 text-sm text-neutral-500">Loading seed suggestions...</p>
          ) : (
            <div className="mt-3 grid gap-3 sm:grid-cols-2 md:grid-cols-3">
              {suggestions.map((item) => {
                const active = selectedSeeds.includes(item.recipeId);
                return (
                  <button
                    key={item.recipeId}
                    type="button"
                    onClick={() => toggleSeedPick(item.recipeId)}
                    className={`rounded-lg border p-3 text-left transition ${
                      active
                        ? "border-emerald-600 bg-emerald-50 ring-2 ring-emerald-500"
                        : "border-neutral-200 hover:border-neutral-400"
                    }`}
                  >
                    <div className="font-medium text-neutral-900">{item.name}</div>
                    <div className="mt-1 text-xs text-neutral-600">
                      {item.cuisines.join(" · ") || "General"}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="border-t border-neutral-200 pt-4">
          <label
            htmlFor="dishSearch"
            className="block text-sm font-semibold text-neutral-800"
          >
            Search Full Dish Catalogue
          </label>
          <input
            id="dishSearch"
            type="search"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search dishes by name (e.g. dal, curry, tofu)..."
            className="mt-1.5 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          />
          {searchResults.length > 0 && (
            <div className="mt-3 grid max-h-60 gap-2 overflow-y-auto sm:grid-cols-2">
              {searchResults.map((dish) => {
                const active = selectedSeeds.includes(dish.recipeId);
                return (
                  <button
                    key={dish.recipeId}
                    type="button"
                    onClick={() => toggleSeedPick(dish.recipeId)}
                    className={`flex items-center justify-between rounded border px-3 py-2 text-left text-sm ${
                      active
                        ? "border-emerald-600 bg-emerald-50 font-semibold"
                        : "border-neutral-200 hover:bg-neutral-50"
                    }`}
                  >
                    <span>{dish.name}</span>
                    <span className="text-xs text-neutral-500">
                      {dish.cuisines.join(", ")}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-4">
          <button
            type="button"
            onClick={() => setStep("profile")}
            className="rounded-lg border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
          >
            Back to Profile
          </button>
          <button
            type="button"
            disabled={
              selectedSeeds.length < 3 ||
              selectedSeeds.length > 5 ||
              confirmSeedsMutation.isPending
            }
            onClick={onSaveSeeds}
            className="rounded-lg bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
          >
            {confirmSeedsMutation.isPending
              ? "Saving Seed Picks..."
              : "Confirm Seed Dishes & Continue"}
          </button>
        </div>
      </div>
    );
  }

  const availableCuisines = cuisinesQuery.data ?? [];

  return (
    <form
      onSubmit={handleSubmit(onSaveProfile)}
      className="mx-auto max-w-3xl space-y-6 rounded-xl border border-neutral-200 bg-white p-6 shadow-sm"
    >
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">
          Onboarding & Nutrition Profile
        </h1>
        <p className="mt-1 text-sm text-neutral-600">
          Configure your physiology, dietary constraints, cuisines, allergies, and clinical conditions.
        </p>
      </div>

      {upsertProfileMutation.error instanceof Error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {upsertProfileMutation.error.message}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
        <div>
          <label className="block text-sm font-medium text-neutral-800">Age (years)</label>
          <input
            type="number"
            {...register("ageYears", { valueAsNumber: true })}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          />
          {errors.ageYears && (
            <p className="mt-1 text-xs text-red-600">{errors.ageYears.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-800">Sex</label>
          <select
            {...register("sex")}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          >
            <option value="FEMALE">Female</option>
            <option value="MALE">Male</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-800">Height (cm)</label>
          <input
            type="number"
            step="0.5"
            {...register("heightCm", { valueAsNumber: true })}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          />
          {errors.heightCm && (
            <p className="mt-1 text-xs text-red-600">{errors.heightCm.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-800">Weight (kg)</label>
          <input
            type="number"
            step="0.5"
            {...register("weightKg", { valueAsNumber: true })}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          />
          {errors.weightKg && (
            <p className="mt-1 text-xs text-red-600">{errors.weightKg.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-800">Activity Level</label>
          <select
            {...register("activity")}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          >
            <option value="SEDENTARY">Sedentary</option>
            <option value="LIGHT">Light</option>
            <option value="MODERATE">Moderate</option>
            <option value="ACTIVE">Active</option>
            <option value="VERY_ACTIVE">Very Active</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-800">Goal</label>
          <select
            {...register("goal")}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          >
            <option value="LOSE">Lose weight</option>
            <option value="MAINTAIN">Maintain weight</option>
            <option value="GAIN">Gain weight</option>
          </select>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-neutral-800">Dietary Pattern</label>
          <select
            {...register("diet")}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          >
            <option value="NONE">No restriction (Omnivore)</option>
            <option value="VEGETARIAN">Vegetarian</option>
            <option value="VEGAN">Vegan</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-800">Cuisine Policy</label>
          <select
            {...register("cuisinePolicy")}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          >
            <option value="MIXED">Mixed (variety across cuisines)</option>
            <option value="MAJORITY">Majority preferred cuisines</option>
            <option value="STRICT">Strict (only selected cuisines)</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-800">
          Preferred Cuisines
        </label>
        <div className="mt-2 flex flex-wrap gap-2">
          {availableCuisines.map((c) => {
            const active = watchedCuisines.includes(c.name);
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => toggleCuisine(c.name)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                  active
                    ? "border-emerald-700 bg-emerald-700 text-white"
                    : "border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-100"
                }`}
              >
                {c.name}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-neutral-800">
            Excluded Ingredients (comma-separated)
          </label>
          <input
            type="text"
            placeholder="e.g. mushroom, cilantro"
            {...register("excludedIngredientsText")}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-800">
            Allergies (comma-separated)
          </label>
          <input
            type="text"
            placeholder="e.g. peanut, shellfish"
            {...register("allergiesText")}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      {watchedAllergiesText.trim().length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3">
          <label className="flex items-start gap-2.5 text-sm text-amber-950">
            <input
              type="checkbox"
              {...register("allergiesConfirmed")}
              className="mt-1 h-4 w-4 rounded border-amber-400"
            />
            <span>
              I explicitly confirm these allergy entries and understand that Savora GC1 uses
              ingredient-name matching rather than a clinical allergen certification.
            </span>
          </label>
          {errors.allergiesConfirmed && (
            <p className="mt-1 text-xs font-medium text-red-600">
              {errors.allergiesConfirmed.message}
            </p>
          )}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-neutral-800">
          Clinical Conditions
        </label>
        <div className="mt-2 flex flex-wrap gap-3">
          {CLINICAL_CONDITIONS.map((cond) => {
            const checked = watchedConditions.includes(cond.id);
            return (
              <label
                key={cond.id}
                className="flex items-center gap-2 rounded-lg border border-neutral-200 px-3 py-2 text-sm"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleCondition(cond.id)}
                />
                <span>{cond.label}</span>
              </label>
            );
          })}
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={upsertProfileMutation.isPending}
          className="rounded-lg bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
        >
          {upsertProfileMutation.isPending
            ? "Calculating Targets..."
            : "Save Profile & Pick Seed Dishes"}
        </button>
      </div>
    </form>
  );
}
