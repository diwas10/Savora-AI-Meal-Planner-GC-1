"use client";

import { HeartPulse, ShieldAlert } from "lucide-react";
import { Controller, useWatch, type UseFormReturn } from "react-hook-form";
import { Chip } from "@/components/ui/Chip";
import { Field, Input, Segmented } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { InlineAlert } from "@/components/ui/States";
import { TagInput } from "@/components/ui/TagInput";
import { cn } from "@/lib/utils";
import { ACTIVITY_OPTIONS, CONDITION_OPTIONS, type ProfileFormValues } from "../schema/profile.schema";
import { useCuisinesQuery } from "../service/profile.query";

type Form = UseFormReturn<ProfileFormValues>;

export function AboutYouSection({ form }: { form: Form }) {
  const { register, control, formState } = form;
  const errors = formState.errors;
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-3 gap-3">
        <Field id="age" label="Age" error={errors.ageYears?.message}>
          <Input id="age" type="number" inputMode="numeric" aria-invalid={Boolean(errors.ageYears)} aria-describedby="age-error" {...register("ageYears", { valueAsNumber: true })} />
        </Field>
        <Field id="height" label="Height (cm)" error={errors.heightCm?.message}>
          <Input id="height" type="number" inputMode="decimal" step="0.5" aria-invalid={Boolean(errors.heightCm)} aria-describedby="height-error" {...register("heightCm", { valueAsNumber: true })} />
        </Field>
        <Field id="weight" label="Weight (kg)" error={errors.weightKg?.message}>
          <Input id="weight" type="number" inputMode="decimal" step="0.1" aria-invalid={Boolean(errors.weightKg)} aria-describedby="weight-error" {...register("weightKg", { valueAsNumber: true })} />
        </Field>
      </div>
      <Controller
        control={control}
        name="sex"
        render={({ field }) => (
          <Segmented
            name="sex"
            label="Sex (used by the energy equation)"
            columns={2}
            value={field.value}
            onChange={field.onChange}
            options={[
              { value: "FEMALE", label: "Female" },
              { value: "MALE", label: "Male" },
            ]}
          />
        )}
      />
      <Controller
        control={control}
        name="activity"
        render={({ field }) => (
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1.5 text-sm font-medium">Activity</legend>
            {ACTIVITY_OPTIONS.map((o) => (
              <label
                key={o.value}
                className={cn(
                  "flex min-h-14 cursor-pointer items-center justify-between gap-3 rounded-2xl px-4 py-2.5 ring-1 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                  field.value === o.value ? "bg-primary-soft ring-primary" : "bg-surface ring-border hover:bg-surface-muted",
                )}
              >
                <span>
                  <span className="block text-[15px] font-medium">{o.label}</span>
                  <span className="block text-xs text-muted-foreground">{o.hint}</span>
                </span>
                <input type="radio" name="activity" value={o.value} checked={field.value === o.value} onChange={() => field.onChange(o.value)} className="size-5 accent-primary" />
              </label>
            ))}
          </fieldset>
        )}
      />
      <Controller
        control={control}
        name="goal"
        render={({ field }) => (
          <Segmented
            name="goal"
            label="Goal"
            value={field.value}
            onChange={field.onChange}
            options={[
              { value: "LOSE", label: "Lose", hint: "weight" },
              { value: "MAINTAIN", label: "Maintain", hint: "weight" },
              { value: "GAIN", label: "Gain", hint: "weight" },
            ]}
          />
        )}
      />
    </div>
  );
}

export function FoodSection({ form }: { form: Form }) {
  const { control, setValue, formState } = form;
  const cuisines = useCuisinesQuery();
  const selected = useWatch({ control, name: "cuisines" });
  const policy = useWatch({ control, name: "cuisinePolicy" });
  const toggle = (name: string) =>
    setValue("cuisines", selected.includes(name) ? selected.filter((c) => c !== name) : [...selected, name], {
      shouldValidate: formState.isSubmitted,
      shouldDirty: true,
    });
  return (
    <div className="flex flex-col gap-6">
      <Controller
        control={control}
        name="diet"
        render={({ field }) => (
          <Segmented
            name="diet"
            label="Diet"
            value={field.value}
            onChange={field.onChange}
            options={[
              { value: "NONE", label: "No rule" },
              { value: "VEGETARIAN", label: "Vegetarian" },
              { value: "VEGAN", label: "Vegan" },
            ]}
          />
        )}
      />
      <Controller
        control={control}
        name="cuisinePolicy"
        render={({ field }) => (
          <Segmented
            name="cuisinePolicy"
            label="How strictly should meals follow your cuisines?"
            value={field.value}
            onChange={field.onChange}
            options={[
              { value: "MIXED", label: "Mix it up", hint: "any cuisine" },
              { value: "MAJORITY", label: "Mostly", hint: "my cuisines" },
              { value: "STRICT", label: "Only", hint: "my cuisines" },
            ]}
          />
        )}
      />
      <fieldset>
        <legend className="mb-2 text-sm font-medium">
          {policy === "MIXED" ? "Favourite cuisines (optional)" : "Your cuisines"}
        </legend>
        {cuisines.isPending ? (
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 10 }, (_, i) => (
              <Skeleton key={i} className="h-11 w-24 rounded-pill" />
            ))}
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {(cuisines.data ?? []).map((c) => (
              <Chip key={c.id} selected={selected.includes(c.name)} onClick={() => toggle(c.name)}>
                {c.name}
              </Chip>
            ))}
          </div>
        )}
        {formState.errors.cuisines?.message && (
          <p role="alert" className="mt-2 text-xs font-medium text-danger">
            {formState.errors.cuisines.message}
          </p>
        )}
      </fieldset>
      <Controller
        control={control}
        name="excludedIngredients"
        render={({ field }) => (
          <Field id="exclusions" label="Ingredients to leave out (optional)" hint="Preferences, not allergies: e.g. beef, pork, mushroom.">
            <TagInput id="exclusions" value={field.value} onChange={field.onChange} placeholder="Type and press Enter" suggestions={["beef", "pork", "mushroom", "onion", "garlic"]} describedBy="exclusions-hint" />
          </Field>
        )}
      />
      <p className="text-xs text-muted-foreground">
        Savora never infers diet or allergies from religion or culture. Only what you choose here applies.
      </p>
    </div>
  );
}

export function HealthSection({ form }: { form: Form }) {
  const { control, register, setValue, formState } = form;
  const allergies = useWatch({ control, name: "allergies" });
  const conditions = useWatch({ control, name: "conditions" });
  const toggle = (value: ProfileFormValues["conditions"][number]) =>
    setValue("conditions", conditions.includes(value) ? conditions.filter((c) => c !== value) : [...conditions, value], { shouldDirty: true });
  return (
    <div className="flex flex-col gap-6">
      <Controller
        control={control}
        name="allergies"
        render={({ field }) => (
          <Field id="allergies" label="Food allergies or intolerances" hint="Ingredients that must never appear in your meals.">
            <TagInput id="allergies" value={field.value} onChange={field.onChange} placeholder="e.g. peanut" suggestions={["peanut", "tree nut", "milk", "egg", "shellfish", "fish", "soy", "wheat", "sesame"]} describedBy="allergies-hint" />
          </Field>
        )}
      />
      {allergies.length > 0 && (
        <div className={cn("rounded-2xl p-4 ring-1", formState.errors.allergiesConfirmed ? "bg-danger-soft ring-danger" : "bg-warning-soft ring-warning-border")}>
          <label className="flex cursor-pointer items-start gap-3 text-sm text-warning-foreground">
            <input type="checkbox" className="mt-0.5 size-5 shrink-0 accent-primary" {...register("allergiesConfirmed")} />
            <span>
              <span className="flex items-center gap-1.5 font-semibold">
                <ShieldAlert className="size-4" aria-hidden /> I confirm these allergies
              </span>
              Savora removes dishes whose ingredient names contain them. It cannot detect hidden or
              derived ingredients, so always check labels.
            </span>
          </label>
          {formState.errors.allergiesConfirmed?.message && (
            <p role="alert" className="mt-2 text-xs font-semibold text-danger">
              {formState.errors.allergiesConfirmed.message}
            </p>
          )}
        </div>
      )}
      <fieldset>
        <legend className="mb-2 text-sm font-medium">Health conditions (optional)</legend>
        <div className="flex flex-wrap gap-2">
          {CONDITION_OPTIONS.map((c) => (
            <Chip key={c.value} selected={conditions.includes(c.value)} onClick={() => toggle(c.value)}>
              {c.label}
            </Chip>
          ))}
        </div>
        {conditions.length > 0 && (
          <InlineAlert tone="info" icon={<HeartPulse className="size-4" aria-hidden />} className="mt-3">
            Recorded for your profile but not yet enforced by the meal rules. Savora is not
            medical advice; follow your clinician&apos;s guidance.
          </InlineAlert>
        )}
      </fieldset>
    </div>
  );
}
