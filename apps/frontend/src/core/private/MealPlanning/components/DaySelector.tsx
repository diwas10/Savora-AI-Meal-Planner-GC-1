"use client";

import { motion } from "motion/react";
import { useRef, type KeyboardEvent } from "react";
import { dayOfMonth, isoDate, weekdayLong, weekdayShort } from "@/lib/format";
import { spring } from "@/lib/motion";
import { cn } from "@/lib/utils";

interface DaySelectorProps {
  dates: string[]; // seven ISO dates, D1..D7
  selected: number; // 1..7
  onSelect: (day: number) => void;
  idPrefix: string;
}

/** Seven-day tablist: arrow keys, Home and End move focus and selection (WAI-ARIA tabs). */
export function DaySelector({ dates, selected, onSelect, idPrefix }: DaySelectorProps) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const today = isoDate(new Date());

  const move = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = dates.length - 1;
    const next =
      event.key === "ArrowRight" ? Math.min(last, index + 1)
      : event.key === "ArrowLeft" ? Math.max(0, index - 1)
      : event.key === "Home" ? 0
      : event.key === "End" ? last
      : null;
    if (next === null) return;
    event.preventDefault();
    onSelect(next + 1);
    refs.current[next]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label="Day of the plan"
      className="scrollbar-none -mx-4 flex snap-x gap-2 overflow-x-auto px-4 py-2 sm:mx-0 sm:px-0"
    >
      {dates.map((date, index) => {
        const day = index + 1;
        const active = day === selected;
        return (
          <button
            key={date}
            ref={(el) => {
              refs.current[index] = el;
            }}
            id={`${idPrefix}-tab-${day}`}
            role="tab"
            type="button"
            aria-selected={active}
            aria-controls={`${idPrefix}-panel`}
            aria-label={`${weekdayLong(date)}${date === today ? ", today" : ""}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onSelect(day)}
            onKeyDown={(e) => move(e, index)}
            className={cn(
              "relative flex h-[72px] min-w-[52px] flex-1 snap-start scroll-ml-4 flex-col items-center justify-center rounded-2xl text-sm transition-colors",
              active ? "text-primary-foreground" : "bg-surface/80 backdrop-blur-md text-foreground ring-1 ring-border hover:bg-surface-muted/90",
            )}
          >
            {active && (
              <motion.span layoutId={`${idPrefix}-day`} className="absolute inset-0 rounded-2xl bg-primary shadow-card" transition={spring} />
            )}
            <span className={cn("relative text-xs font-medium", active ? "opacity-90" : "text-muted-foreground")}>
              {weekdayShort(date)}
            </span>
            <span className="relative text-lg font-bold tabular-nums">{dayOfMonth(date)}</span>
            {date === today && (
              <span className={cn("relative mt-0.5 size-1.5 rounded-pill", active ? "bg-primary-foreground" : "bg-accent")} aria-hidden />
            )}
          </button>
        );
      })}
    </div>
  );
}
