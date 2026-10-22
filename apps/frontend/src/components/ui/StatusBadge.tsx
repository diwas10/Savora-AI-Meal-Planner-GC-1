import type { Schema } from "@savora/contracts";
import { CircleCheck, CircleX, Clock, LoaderCircle, TriangleAlert } from "lucide-react";
import { Badge } from "./Badge";

type Status = Schema<"MealPlanJobStatus">;

const STATUS: Record<Status, { label: string; tone: "primary" | "success" | "warning" | "danger" | "info"; Icon: typeof Clock }> = {
  GENERATING: { label: "Preparing", tone: "info", Icon: LoaderCircle },
  FEASIBLE: { label: "Ready", tone: "success", Icon: CircleCheck },
  INFEASIBLE: { label: "No feasible week", tone: "warning", Icon: TriangleAlert },
  INSUFFICIENT_DATA: { label: "Not enough meals", tone: "warning", Icon: TriangleAlert },
  TIMEOUT: { label: "Timed out", tone: "warning", Icon: Clock },
  FAILED: { label: "Failed", tone: "danger", Icon: CircleX },
};

export function StatusBadge({ status }: { status: Status }) {
  const { label, tone, Icon } = STATUS[status];
  return (
    <Badge tone={tone}>
      <Icon className={status === "GENERATING" ? "size-3.5 animate-spin" : "size-3.5"} aria-hidden />
      {label}
    </Badge>
  );
}
