"use client";

import type { Schema } from "@savora/contracts";
import { ChevronRight, Flame } from "lucide-react";
import { motion } from "motion/react";
import { Badge } from "@/components/ui/Badge";
import { dishName, nutrient } from "@/lib/format";
import { fadeUp } from "@/lib/motion";

type CravingItem = Schema<"CravingItem">;

export function RecipeCard({ item, onOpen }: { item: CravingItem; onOpen: () => void }) {
  const name = dishName(item.name);
  const n = item.explanation.standardNutrients;
  return (
    <motion.li variants={fadeUp}>
      <button
        type="button"
        onClick={onOpen}
        className="group flex w-full items-start gap-3 rounded-2xl bg-surface p-3.5 text-left ring-1 ring-border transition-shadow hover:shadow-card"
        aria-label={`${item.rank}. ${name.title}. View details`}
      >
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-sm font-bold tabular-nums text-accent-soft-foreground">
          {item.rank}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold leading-snug">{name.title}</p>
          {name.subtitle && <p className="truncate text-xs text-muted-foreground">{name.subtitle}</p>}
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {item.cuisines.slice(0, 2).map((c) => (
              <Badge key={c}>{c}</Badge>
            ))}
            <span className="inline-flex items-center gap-1 text-xs font-medium text-foreground">
              <Flame className="size-3.5 text-chart-energy" aria-hidden />
              {nutrient(n.energyKcal, "kcal")}
            </span>
            <span className="text-xs text-muted-foreground">· {item.explanation.standardPortion}</span>
          </div>
        </div>
        <ChevronRight className="mt-2 size-4 shrink-0 text-subtle-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
      </button>
    </motion.li>
  );
}
