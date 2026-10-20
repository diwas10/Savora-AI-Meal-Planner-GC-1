import { z } from "zod";

export const profileFormSchema = z
  .object({
    ageYears: z.number().int().min(18, "Must be at least 18").max(100, "Max age is 100"),
    sex: z.enum(["FEMALE", "MALE"]),
    heightCm: z.number().min(120, "Min height 120 cm").max(230, "Max height 230 cm"),
    weightKg: z.number().min(35, "Min weight 35 kg").max(250, "Max weight 250 kg"),
    activity: z.enum(["SEDENTARY", "LIGHT", "MODERATE", "ACTIVE", "VERY_ACTIVE"]),
    goal: z.enum(["LOSE", "MAINTAIN", "GAIN"]),
    diet: z.enum(["NONE", "VEGETARIAN", "VEGAN"]),
    cuisinePolicy: z.enum(["STRICT", "MAJORITY", "MIXED"]),
    cuisines: z.array(z.string()),
    excludedIngredientsText: z.string(),
    allergiesText: z.string(),
    allergiesConfirmed: z.boolean(),
    conditions: z.array(z.enum(["TYPE_2_DIABETES", "HYPERTENSION", "DYSLIPIDEMIA"])),
  })
  .superRefine((values, ctx) => {
    const allergies = values.allergiesText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (allergies.length > 0 && !values.allergiesConfirmed) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["allergiesConfirmed"],
        message: "You must explicitly confirm your allergy selections.",
      });
    }
  });

export type ProfileFormValues = z.infer<typeof profileFormSchema>;
