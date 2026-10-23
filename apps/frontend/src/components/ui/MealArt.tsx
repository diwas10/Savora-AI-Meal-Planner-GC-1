import type { Schema } from "@savora/contracts";
import { Coffee, Moon, Salad, Soup, Sunrise, UtensilsCrossed } from "lucide-react";
import { cn } from "@/lib/utils";

type MealType = Schema<"MealType">;

const ART: Record<MealType, { className: string; Icon: typeof Coffee; Accent: typeof Coffee }> = {
  BREAKFAST: {
    className: "from-meal-breakfast-from to-meal-breakfast-to text-meal-breakfast-ink",
    Icon: Coffee,
    Accent: Sunrise,
  },
  LUNCH: {
    className: "from-meal-lunch-from to-meal-lunch-to text-meal-lunch-ink",
    Icon: Salad,
    Accent: UtensilsCrossed,
  },
  DINNER: {
    className: "from-meal-dinner-from to-meal-dinner-to text-meal-dinner-ink",
    Icon: Soup,
    Accent: Moon,
  },
};

/**
 * The illustrated fallback used in place of food photography: GC1 has no licensed dish
 * images, so every card is fully understandable without one (DESIGN_SYSTEM principle 3).
 */
export function MealArt({
  mealType,
  label,
  className,
  size = "md",
}: {
  mealType: MealType;
  label: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const { className: tone, Icon, Accent } = ART[mealType];
  return (
    <div
      role="img"
      aria-label={label}
      className={cn(
        "relative isolate grid shrink-0 place-items-center overflow-hidden bg-gradient-to-br",
        tone,
        size === "sm" && "size-14 rounded-2xl",
        size === "md" && "size-20 rounded-3xl",
        size === "lg" && "h-40 w-full rounded-card",
        className,
      )}
    >
      <Accent className="absolute -right-2 -top-2 size-12 opacity-20" aria-hidden />
      <Icon className={cn(size === "lg" ? "size-14" : size === "sm" ? "size-6" : "size-8")} strokeWidth={1.6} aria-hidden />
    </div>
  );
}
