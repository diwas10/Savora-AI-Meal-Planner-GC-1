import type { Schema } from "@savora/contracts";
import { dishTitle } from "@/lib/format";

type MealExplanation = Schema<"MealExplanation">;
type Reason = Schema<"Reason">;
type ReasonKind = Schema<"ReasonKind">;

const ROLE_LABEL: Record<string, string> = {
  MAIN_DISH: "Main",
  BREAKFAST_BASE: "Breakfast",
  STAPLE: "Staple",
  VEGETABLE_SIDE: "Side",
  FRUIT: "Fruit",
  PROTEIN_SOURCE: "Protein",
  SNACK: "Snack",
};

export function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role.charAt(0) + role.slice(1).toLowerCase().replaceAll("_", " ");
}

/** "Chana Masala" + "with steamed white rice and roti" from the meal's dishes. */
export function mealTitle(explanation: MealExplanation): { title: string; withText: string | null } {
  const [anchor, ...rest] = explanation.dishes;
  const title = anchor ? dishTitle(anchor.name) : "Meal";
  const others = rest.map((d) => dishTitle(d.name).toLowerCase());
  if (others.length === 0) return { title, withText: null };
  const joined = others.length === 1 ? others[0] : `${others.slice(0, -1).join(", ")} and ${others.at(-1)}`;
  return { title, withText: `with ${joined}` };
}

export const REASON_LABEL: Record<ReasonKind, string> = {
  RULES: "Rule check",
  RANKING: "Why it was ranked",
  COMPOSITION: "How it was put together",
  PORTION: "Portions",
  NUTRITION: "Nutrition data",
  PLANNING: "Week check",
  LIMITATION: "Limits",
};

const REASON_ORDER: ReasonKind[] = ["RULES", "PLANNING", "RANKING", "COMPOSITION", "PORTION", "NUTRITION", "LIMITATION"];

export function reasonsByKind(reasons: Reason[]): Array<[ReasonKind, Reason[]]> {
  return REASON_ORDER.map((kind) => [kind, reasons.filter((r) => r.kind === kind)] as [ReasonKind, Reason[]]).filter(
    ([, list]) => list.length > 0,
  );
}

export const SOURCE_LABEL: Record<Schema<"NutritionSource">, string> = {
  FOODCOM_DERIVED: "Food.com (derived)",
  USDA_FNDDS: "USDA FNDDS",
  USDA_SR_LEGACY: "USDA SR Legacy",
  USDA_FOUNDATION: "USDA Foundation",
  CURATED: "Curated",
};
