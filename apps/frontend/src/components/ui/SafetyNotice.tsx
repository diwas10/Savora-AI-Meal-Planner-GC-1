import type { Schema } from "@savora/contracts";
import { ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

type SafetyVerification = Schema<"SafetyVerification">;

const CONDITION_LABEL: Record<Schema<"HealthCondition">, string> = {
  TYPE_2_DIABETES: "type 2 diabetes",
  HYPERTENSION: "hypertension",
  DYSLIPIDEMIA: "dyslipidemia",
};

/**
 * Shown wherever results appear (spec section 1). Opaque surface, never glass; it never
 * says "safe for you" - the rules are a stand-in until the production KB lands.
 */
export function SafetyNotice({
  safety,
  compact = false,
  className,
}: {
  safety?: SafetyVerification | null;
  compact?: boolean;
  className?: string;
}) {
  if (!safety) return null;
  const conditions = safety.conditionsNotEnforced.map((c) => CONDITION_LABEL[c]);
  return (
    <aside
      role="note"
      aria-label="How these results were checked"
      className={cn(
        "flex gap-3 rounded-2xl bg-warning-soft p-3.5 text-sm text-warning-foreground ring-1 ring-warning-border",
        className,
      )}
    >
      <ShieldAlert className="mt-0.5 size-5 shrink-0" aria-hidden />
      <div className="min-w-0">
        <p className="font-semibold">Checked by stand-in rules, not verified</p>
        {!compact && <p className="mt-0.5 leading-relaxed">{safety.message}</p>}
        {conditions.length > 0 && (
          <p className="mt-1 text-xs">Not enforced yet: {conditions.join(", ")}.</p>
        )}
      </div>
    </aside>
  );
}
