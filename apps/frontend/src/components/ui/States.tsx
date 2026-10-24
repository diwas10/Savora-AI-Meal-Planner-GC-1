import { CloudOff, RefreshCw, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Button } from "./Button";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-10 text-center", className)}>
      <div className="mb-4 grid size-16 place-items-center rounded-3xl bg-primary-soft text-primary-soft-foreground">
        {icon}
      </div>
      <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  offline?: boolean;
}

export function ErrorState({ title = "Something went wrong", message, onRetry, offline = false }: ErrorStateProps) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-10 text-center">
      <div className="mb-4 grid size-14 place-items-center rounded-3xl bg-danger-soft text-danger-foreground">
        {offline ? <CloudOff className="size-6" aria-hidden /> : <TriangleAlert className="size-6" aria-hidden />}
      </div>
      <h3 className="text-base font-semibold">{offline ? "You're offline" : title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry} icon={<RefreshCw className="size-4" aria-hidden />}>
          Try again
        </Button>
      )}
    </div>
  );
}

const ALERT_TONES = {
  info: "bg-info-soft/85 backdrop-blur-sm text-info-foreground",
  warning: "bg-warning-soft/85 backdrop-blur-sm text-warning-foreground ring-1 ring-warning-border",
  danger: "bg-danger-soft/85 backdrop-blur-sm text-danger-foreground",
  success: "bg-success-soft/85 backdrop-blur-sm text-success-foreground",
} as const;

export function InlineAlert({
  tone = "info",
  icon,
  title,
  children,
  className,
}: {
  tone?: keyof typeof ALERT_TONES;
  icon?: ReactNode;
  title?: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div role={tone === "danger" ? "alert" : "note"} className={cn("flex gap-3 rounded-2xl p-3.5 text-sm", ALERT_TONES[tone], className)}>
      {icon && <span className="mt-0.5 shrink-0">{icon}</span>}
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn(title && "mt-0.5")}>{children}</div>}
      </div>
    </div>
  );
}
