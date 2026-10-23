"use client";

import { Check, Heart, Search } from "lucide-react";
import { motion } from "motion/react";
import { useDeferredValue, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState, InlineAlert } from "@/components/ui/States";
import { ApiError } from "@/lib/api-request";
import { dishName } from "@/lib/format";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { useConfirmSeedPicksMutation, useDishSearchQuery, useSeedSuggestionsQuery } from "../service/profile.query";

const MIN = 3;
const MAX = 5;

interface Dish {
  recipeId: string;
  name: string;
  cuisines: string[];
  /** Excluded ingredients this dish uses and what to cook with instead (never allergies). */
  swaps?: { ingredient: string; instead: string }[];
}

/** ADR 0005: 3-5 liked dishes give the ranker a starting history (cold start). */
export function SeedPicker({ initial, onDone }: { initial: string[]; onDone: () => void }) {
  const suggestions = useSeedSuggestionsQuery();
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query.trim());
  const search = useDishSearchQuery(deferred);
  const confirm = useConfirmSeedPicksMutation();
  const [picked, setPicked] = useState<string[]>(initial);

  const list: Dish[] = deferred
    ? (search.data ?? []).map((d) => ({ ...d, cuisines: [...d.cuisines] }))
    : (suggestions.data?.suggestions ?? []).map((s) => ({ ...s, cuisines: [...s.cuisines], swaps: [...(s.swaps ?? [])] }));
  const count = picked.length;

  const toggle = (id: string) =>
    setPicked((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : prev.length >= MAX ? prev : [...prev, id],
    );

  const save = async () => {
    await confirm.mutateAsync({ recipeIds: picked });
    onDone();
  };

  const error = confirm.error instanceof ApiError ? confirm.error.message : confirm.error ? "Could not save your picks." : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-subtle-foreground" aria-hidden />
        <label htmlFor="dish-search" className="sr-only">
          Search dishes
        </label>
        <Input id="dish-search" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search dishes or cuisines" className="pl-12" />
      </div>

      {(deferred ? search.isPending : suggestions.isPending) ? (
        <div className="grid grid-cols-2 gap-2.5">
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : suggestions.isError && !deferred ? (
        <ErrorState message="We couldn't load suggestions." onRetry={() => void suggestions.refetch()} />
      ) : list.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">No dishes match “{deferred}”.</p>
      ) : (
        <motion.ul variants={stagger} initial="hidden" animate="show" className="grid grid-cols-2 gap-2.5" aria-label="Dishes">
          {list.map((dish) => {
            const name = dishName(dish.name);
            const on = picked.includes(dish.recipeId);
            return (
              <motion.li key={dish.recipeId} variants={fadeUp}>
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(dish.recipeId)}
                  className={cn(
                    "relative flex h-full min-h-24 w-full flex-col justify-between rounded-2xl p-3 text-left ring-1 transition-[box-shadow,background-color] active:scale-[0.98]",
                    on ? "bg-primary-soft ring-2 ring-primary" : "bg-surface ring-border hover:shadow-card",
                  )}
                >
                  <span className="pr-6 text-sm font-semibold leading-snug">{name.title}</span>
                  {dish.swaps && dish.swaps.length > 0 && (
                    <span className="mt-1.5 flex flex-col gap-0.5 text-[11px] leading-snug" aria-label="Cook it with these swaps">
                      {dish.swaps.map((s) => (
                        <span key={s.ingredient}>
                          <span className="text-accent">No {s.ingredient}:</span>{" "}
                          <span className="text-muted-foreground">use {s.instead}</span>
                        </span>
                      ))}
                    </span>
                  )}
                  <span className="mt-2 truncate text-xs text-muted-foreground">{dish.cuisines.join(" · ")}</span>
                  <span
                    className={cn(
                      "absolute right-2.5 top-2.5 grid size-6 place-items-center rounded-pill",
                      on ? "bg-primary text-primary-foreground" : "bg-surface-muted text-subtle-foreground",
                    )}
                    aria-hidden
                  >
                    {on ? <Check className="size-3.5" /> : <Heart className="size-3.5" />}
                  </span>
                </button>
              </motion.li>
            );
          })}
        </motion.ul>
      )}

      {error && <InlineAlert tone="danger">{error}</InlineAlert>}

      <div className="sticky bottom-0 -mx-1 flex items-center gap-3 bg-background/90 px-1 py-3 backdrop-blur-sm">
        <p className="flex-1 text-sm" aria-live="polite">
          <span className="font-semibold tabular-nums">{count}</span> of {MIN}–{MAX} picked
        </p>
        <Button size="lg" disabled={count < MIN} loading={confirm.isPending} onClick={() => void save()}>
          Save favourites
        </Button>
      </div>
    </div>
  );
}
