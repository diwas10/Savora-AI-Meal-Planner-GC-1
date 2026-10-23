import { cn } from "@/lib/utils";

interface RangeBarProps {
  label: string;
  unit: string;
  planned: number | null | undefined;
  min?: number | null;
  max?: number | null;
  className?: string;
}

/**
 * Planned amount against the profile's target band. Deliberately NOT a progress bar:
 * GC1 plans meals, it does not track what was eaten (DESIGN_SYSTEM principle 5).
 */
export function RangeBar({ label, unit, planned, min, max, className }: RangeBarProps) {
  const known = planned !== null && planned !== undefined;
  const hasBand = min !== null && min !== undefined && max !== null && max !== undefined && max > 0;
  const scale = Math.max(hasBand ? max * 1.3 : 0, known ? planned * 1.1 : 0, 1);
  const pct = (v: number) => `${Math.min(100, (v / scale) * 100)}%`;
  const status = !known || !hasBand ? null : planned < min ? "below" : planned > max ? "above" : "within";
  const fmt = (v: number) => new Intl.NumberFormat("en", { maximumFractionDigits: 0 }).format(v);
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium">{label}</span>
        <span className="tabular-nums text-muted-foreground">
          <span className="font-semibold text-foreground">{known ? fmt(planned) : "unknown"}</span>
          {known && ` ${unit}`}
          {hasBand && (
            <span className="text-xs">
              {" "}· target {fmt(min)}–{fmt(max)}
            </span>
          )}
        </span>
      </div>
      <div className="relative h-2.5 rounded-pill bg-range-track" aria-hidden>
        {hasBand && (
          <div
            className="absolute inset-y-0 rounded-pill bg-range-band"
            style={{ left: pct(min), width: `calc(${pct(max)} - ${pct(min)})` }}
          />
        )}
        {known && (
          <div
            className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-pill border-2 border-surface bg-primary shadow-card"
            style={{ left: pct(planned) }}
          />
        )}
      </div>
      {status && (
        <p className="text-xs text-muted-foreground">
          Planned amount is {status === "within" ? "within" : status} the estimated range
        </p>
      )}
    </div>
  );
}
