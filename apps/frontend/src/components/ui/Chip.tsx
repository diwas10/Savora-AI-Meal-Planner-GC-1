"use client";

import { Check } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  selected?: boolean;
}

/** A toggle chip: a real button with aria-pressed (keyboard and screen-reader friendly). */
export function Chip({ selected = false, className, children, type = "button", ...props }: ChipProps) {
  return (
    <button
      type={type}
      aria-pressed={selected}
      className={cn(
        "inline-flex min-h-11 items-center gap-1.5 rounded-pill px-4 text-sm font-medium ring-1 transition-colors active:scale-[0.97]",
        selected
          ? "bg-primary text-primary-foreground ring-primary"
          : "bg-surface text-foreground ring-border hover:bg-surface-muted",
        className,
      )}
      {...props}
    >
      {selected && <Check className="size-3.5" aria-hidden />}
      {children}
    </button>
  );
}

/** A suggestion chip (sends a ready-made prompt). */
export function SuggestionChip({ className, type = "button", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-pill bg-surface px-3.5 text-sm font-medium text-foreground ring-1 ring-border transition-colors hover:bg-surface-muted active:scale-[0.97]",
        className,
      )}
      {...props}
    />
  );
}
