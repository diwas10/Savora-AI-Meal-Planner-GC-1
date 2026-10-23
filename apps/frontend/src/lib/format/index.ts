import type { Schema } from "@savora/contracts";

type NutrientVector = Schema<"NutrientVector">;
type MealType = Schema<"MealType">;

const SMALL_WORDS = new Set(["and", "with", "or", "of", "in", "a", "the", "on", "for", "to"]);

function titleCase(text: string): string {
  return text
    .split(" ")
    .filter(Boolean)
    .map((word, i) =>
      i > 0 && SMALL_WORDS.has(word) ? word : word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

/**
 * Food.com names are lower-case with runs of spaces where punctuation was removed:
 * "alu paratha   mashed potato stuffed bread" -> { title: "Alu Paratha", subtitle: "Mashed..." }.
 */
export function dishName(raw: string): { title: string; subtitle: string | null } {
  const [head, ...rest] = raw.trim().split(/\s{2,}/);
  const subtitle = rest.join(" ").trim();
  return { title: titleCase(head ?? raw), subtitle: subtitle ? titleCase(subtitle) : null };
}

export function dishTitle(raw: string): string {
  return dishName(raw).title;
}

const NUMBER = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });

/** A nutrient value with its unit, or "unknown" (never 0 for missing data). */
export function nutrient(value: number | null | undefined, unit: "kcal" | "g" | "mg"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "unknown";
  return `${NUMBER.format(value)}${unit === "kcal" ? " kcal" : ` ${unit}`}`;
}

export const NUTRIENT_ROWS: ReadonlyArray<{
  key: keyof NutrientVector;
  label: string;
  unit: "kcal" | "g" | "mg";
}> = [
  { key: "energyKcal", label: "Energy", unit: "kcal" },
  { key: "proteinG", label: "Protein", unit: "g" },
  { key: "carbohydrateG", label: "Carbohydrate", unit: "g" },
  { key: "fatG", label: "Fat", unit: "g" },
  { key: "saturatedFatG", label: "Saturated fat", unit: "g" },
  { key: "sugarsG", label: "Sugars", unit: "g" },
  { key: "sodiumMg", label: "Sodium", unit: "mg" },
];

export const MEAL_LABEL: Record<MealType, string> = {
  BREAKFAST: "Breakfast",
  LUNCH: "Lunch",
  DINNER: "Dinner",
};

export const MEAL_ORDER: MealType[] = ["BREAKFAST", "LUNCH", "DINNER"];

/** "D3_DINNER" -> { day: 3, meal: "DINNER" } */
export function parseSlot(slotId: string): { day: number; meal: MealType } | null {
  const match = /^D([1-7])_(BREAKFAST|LUNCH|DINNER)$/.exec(slotId);
  if (!match) return null;
  return { day: Number(match[1]), meal: match[2] as MealType };
}

/** Parse "YYYY-MM-DD" as a local calendar date (no timezone shift). */
export function localDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1);
}

export function isoDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function weekdayShort(iso: string): string {
  return localDate(iso).toLocaleDateString("en", { weekday: "short" });
}

export function weekdayLong(iso: string): string {
  return localDate(iso).toLocaleDateString("en", { weekday: "long" });
}

export function dayOfMonth(iso: string): string {
  return String(localDate(iso).getDate());
}

export function longDate(iso: string): string {
  return localDate(iso).toLocaleDateString("en", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

export function shortRange(startIso: string): string {
  const start = localDate(startIso);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  const fmt = (d: Date) => d.toLocaleDateString("en", { month: "short", day: "numeric" });
  return `${fmt(start)} – ${fmt(end)}`;
}

/** The next Monday on or after today (plans run Monday to Sunday by default). */
export function nextMonday(from: Date = new Date()): string {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  const offset = (8 - d.getDay()) % 7;
  d.setDate(d.getDate() + offset);
  return isoDate(d);
}

export function relativeTime(iso: string): string {
  const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const steps: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 31536000],
    ["month", 2592000],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

export function greeting(now: Date = new Date()): string {
  const hour = now.getHours();
  if (hour < 5) return "Good evening";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/** "MIDDLE_EASTERN" -> "Middle Eastern" */
export function cuisineLabel(id: string): string {
  return id
    .split("_")
    .map((p) => p.charAt(0) + p.slice(1).toLowerCase())
    .join(" ");
}

export const FLAVOR_LABEL: Record<Schema<"FlavorTag">, string> = {
  SPICY: "Spicy",
  SWEET: "Sweet",
  SOUR: "Sour",
  SMOKY: "Smoky",
  CREAMY: "Creamy",
};

export function ingredientLabel(id: string): string {
  return id.toLowerCase().replaceAll("_", " ");
}
