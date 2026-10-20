import type { Schema } from "@savora/contracts";

type SafetyVerification = Schema<"SafetyVerification">;

interface SafetyNoticeProps {
  safety?: SafetyVerification | null;
  className?: string;
}

export function SafetyNotice({ safety, className = "" }: SafetyNoticeProps) {
  if (!safety) {
    return null;
  }

  return (
    <div
      role="note"
      aria-label="Dietary and allergen verification notice"
      className={`rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 ${className}`}
    >
      <div className="flex flex-wrap items-center gap-2 font-semibold">
        <span>Verification Status: {safety.status}</span>
        <span className="rounded bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-900">
          Diet: {safety.dietCheckedBy}
        </span>
        <span className="rounded bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-900">
          Allergens: {safety.allergensCheckedBy}
        </span>
      </div>
      <p className="mt-1.5 leading-relaxed">{safety.message}</p>
      {safety.conditionsNotEnforced && safety.conditionsNotEnforced.length > 0 && (
        <p className="mt-1 text-xs font-medium text-amber-900">
          Clinical conditions not enforced in this stand-in rule set:{" "}
          {safety.conditionsNotEnforced.join(", ")}
        </p>
      )}
    </div>
  );
}
