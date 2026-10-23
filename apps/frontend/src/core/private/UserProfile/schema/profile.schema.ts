import type { Schema } from "@savora/contracts";
import { z } from "zod";

/** Mirrors the backend's ProfileUpsertRequest limits so errors show inline, not after a 422. */
export const profileFormSchema = z
  .object({
    ageYears: z.number({ error: "Enter your age" }).int("Whole years only").min(19, "Savora's estimates are for adults (19+)").max(100, "Maximum age is 100"),
    sex: z.enum(["FEMALE", "MALE"]),
    heightCm: z.number({ error: "Enter your height" }).min(100, "Minimum 100 cm").max(250, "Maximum 250 cm"),
    weightKg: z.number({ error: "Enter your weight" }).min(30, "Minimum 30 kg").max(300, "Maximum 300 kg"),
    activity: z.enum(["SEDENTARY", "LIGHT", "MODERATE", "ACTIVE", "VERY_ACTIVE"]),
    goal: z.enum(["LOSE", "MAINTAIN", "GAIN"]),
    diet: z.enum(["NONE", "VEGETARIAN", "VEGAN"]),
    cuisinePolicy: z.enum(["STRICT", "MAJORITY", "MIXED"]).refine(
      (policy): boolean => policy !== "MAJORITY",
      "Mostly is unavailable in this prototype. Choose Mix it up or Only.",
    ),
    cuisines: z.array(z.string()).max(25),
    excludedIngredients: z.array(z.string().min(1).max(60)).max(50),
    allergies: z.array(z.string().min(1).max(60)).max(50),
    allergiesConfirmed: z.boolean(),
    conditions: z.array(z.enum(["TYPE_2_DIABETES", "HYPERTENSION", "DYSLIPIDEMIA"])),
  })
  .superRefine((v, ctx) => {
    if (v.allergies.length > 0 && !v.allergiesConfirmed) {
      ctx.addIssue({
        code: "custom",
        path: ["allergiesConfirmed"],
        message: "Please confirm your allergies so Savora can apply them",
      });
    }
    if (v.cuisinePolicy !== "MIXED" && v.cuisines.length === 0) {
      ctx.addIssue({ code: "custom", path: ["cuisines"], message: "Pick at least one cuisine" });
    }
  });

export type ProfileFormValues = z.infer<typeof profileFormSchema>;

type UserProfileDto = Schema<"UserProfileDto">;
type ProfileUpsertRequest = Schema<"ProfileUpsertRequest">;

export const DEFAULT_PROFILE: ProfileFormValues = {
  ageYears: 30,
  sex: "FEMALE",
  heightCm: 165,
  weightKg: 62,
  activity: "MODERATE",
  goal: "MAINTAIN",
  diet: "NONE",
  cuisinePolicy: "MIXED",
  cuisines: [],
  excludedIngredients: [],
  allergies: [],
  allergiesConfirmed: false,
  conditions: [],
};

export function toFormValues(profile: UserProfileDto | undefined): ProfileFormValues {
  if (!profile) return DEFAULT_PROFILE;
  return {
    ageYears: profile.ageYears,
    sex: profile.sex,
    heightCm: profile.heightCm,
    weightKg: profile.weightKg,
    activity: profile.activity,
    goal: profile.goal,
    diet: profile.diet ?? "NONE",
    cuisinePolicy: profile.cuisinePolicy,
    cuisines: profile.cuisines,
    excludedIngredients: profile.excludedIngredients,
    allergies: profile.allergies,
    allergiesConfirmed: Boolean(profile.allergiesConfirmedAt),
    conditions: profile.conditions,
  };
}

export function toUpsertRequest(v: ProfileFormValues): ProfileUpsertRequest {
  if (v.cuisinePolicy === "MAJORITY") {
    throw new Error("Choose MIXED or STRICT; MAJORITY is not supported.");
  }
  return {
    ageYears: v.ageYears,
    sex: v.sex,
    heightCm: v.heightCm,
    weightKg: v.weightKg,
    activity: v.activity,
    goal: v.goal,
    diet: v.diet === "NONE" ? null : v.diet,
    cuisinePolicy: v.cuisinePolicy,
    cuisines: v.cuisinePolicy === "MIXED" && v.cuisines.length === 0 ? [] : v.cuisines,
    excludedIngredients: v.excludedIngredients,
    allergies: v.allergies,
    allergiesConfirmed: v.allergies.length > 0 ? v.allergiesConfirmed : false,
    conditions: v.conditions,
  };
}

export const ACTIVITY_OPTIONS = [
  { value: "SEDENTARY", label: "Mostly sitting", hint: "desk work, little exercise" },
  { value: "LIGHT", label: "Lightly active", hint: "walks, light exercise 1–3 days" },
  { value: "MODERATE", label: "Moderately active", hint: "exercise 3–5 days" },
  { value: "ACTIVE", label: "Very active", hint: "hard exercise 6–7 days" },
  { value: "VERY_ACTIVE", label: "Athlete", hint: "physical job or twice-daily training" },
] as const;

export const CONDITION_OPTIONS = [
  { value: "TYPE_2_DIABETES", label: "Type 2 diabetes" },
  { value: "HYPERTENSION", label: "High blood pressure" },
  { value: "DYSLIPIDEMIA", label: "High cholesterol" },
] as const;
