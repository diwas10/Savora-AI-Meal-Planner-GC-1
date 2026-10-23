import type { Schema } from "@savora/contracts";

type NutritionTargets = Schema<"NutritionTargets">;
type Profile = Schema<"UserProfileDto">;

/**
 * The inputs of the backend's target calculator (apps/ai_system .../nutrition/targets.py,
 * formula `targets-0.2`), mirrored only to EXPLAIN a stored result. The explanation is shown
 * only when it reproduces the stored energy target exactly, so a change to the backend
 * constants hides the breakdown instead of showing numbers that disagree with the targets.
 */
const SEX_CONSTANT = { MALE: 5, FEMALE: -161 } as const;
const ACTIVITY_FACTOR = { SEDENTARY: 1.2, LIGHT: 1.375, MODERATE: 1.55, ACTIVE: 1.725, VERY_ACTIVE: 1.9 } as const;
const GOAL_FACTOR = { LOSE: 0.85, MAINTAIN: 1, GAIN: 1.1 } as const;
const BAND_FRACTION = 0.05;
const PROTEIN_RDA_G_PER_KG = 0.8;

/** Share of energy and Atwater kcal per gram (IOM 2005 AMDR, adults). */
export const MACRO_SHARE: Record<string, { low: number; high: number; kcalPerG: number }> = {
  protein_g: { low: 0.1, high: 0.35, kcalPerG: 4 },
  carbohydrate_g: { low: 0.45, high: 0.65, kcalPerG: 4 },
  fat_g: { low: 0.2, high: 0.35, kcalPerG: 9 },
};

export interface TargetBreakdown {
  resting: number;
  activityFactor: number;
  maintenance: number;
  goalFactor: number;
  target: number;
  band: number;
  proteinFloor: { rda: number; amdrMin: number; usesRda: boolean };
  inputs: { weightKg: number; heightCm: number; ageYears: number; sexConstant: number };
}

/** The energy steps for this profile, or null when they do not reproduce the stored target. */
export function explainTargets(targets: NutritionTargets, profile: Profile | undefined): TargetBreakdown | null {
  if (!profile || targets.formulaVersion !== "targets-0.2") return null;
  const sexConstant = SEX_CONSTANT[profile.sex as keyof typeof SEX_CONSTANT];
  const activityFactor = ACTIVITY_FACTOR[profile.activity as keyof typeof ACTIVITY_FACTOR];
  const goalFactor = GOAL_FACTOR[profile.goal as keyof typeof GOAL_FACTOR];
  if (sexConstant === undefined || activityFactor === undefined || goalFactor === undefined) return null;
  const resting = 10 * profile.weightKg + 6.25 * profile.heightCm - 5 * profile.ageYears + sexConstant;
  const target = Math.round(resting * activityFactor * goalFactor);
  if (target !== targets.energyKcal.target) return null;
  const rda = Math.round(PROTEIN_RDA_G_PER_KG * profile.weightKg);
  const amdrMin = Math.round((target * MACRO_SHARE.protein_g.low) / MACRO_SHARE.protein_g.kcalPerG);
  return {
    resting,
    activityFactor,
    maintenance: resting * activityFactor,
    goalFactor,
    target,
    band: Math.round(target * BAND_FRACTION),
    proteinFloor: { rda, amdrMin, usesRda: rda > amdrMin },
    inputs: {
      weightKg: profile.weightKg,
      heightCm: profile.heightCm,
      ageYears: profile.ageYears,
      sexConstant,
    },
  };
}
