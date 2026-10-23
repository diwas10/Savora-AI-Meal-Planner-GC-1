import { useId } from "react";
import { cn } from "@/lib/utils";

/** The Savora mark: a leaf-and-bowl glyph on the brand gradient. */
export function BrandMark({ className }: { className?: string }) {
  const id = `savora-mark-${useId().replace(/:/g, "")}`;
  return (
    <svg viewBox="0 0 64 64" className={cn("size-9", className)} role="img" aria-label="Savora">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--hero-from)" />
          <stop offset="0.55" stopColor="var(--hero-via)" />
          <stop offset="1" stopColor="var(--hero-to)" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="18" fill={`url(#${id})`} />
      <path d="M14 34h36a18 18 0 0 1-36 0Z" fill="var(--hero-ink)" opacity="0.95" />
      <path
        d="M33 30c0-9 6-15 15-16-1 9-6 15-15 16Z"
        fill="var(--hero-ink)"
        opacity="0.85"
      />
      <path d="M31 30c-1-6-5-10-11-11 0 6 4 10 11 11Z" fill="var(--hero-ink)" opacity="0.6" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="text-xl font-bold tracking-tight">Savora</span>
    </span>
  );
}
