import type { ReactNode } from "react";
import { ThemeToggle } from "@/core/common/theme/ThemeToggle";
import { cn } from "@/lib/utils";

/** Page title area with safe spacing below the status bar in standalone mode. */
export function PageHeader({
  eyebrow,
  title,
  description,
  action,
  showThemeToggle = true,
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  showThemeToggle?: boolean;
  className?: string;
}) {
  return (
    <header className={cn("flex items-end justify-between gap-4 pb-5 pt-6 lg:pt-10", className)}>
      <div className="min-w-0">
        {eyebrow && <p className="text-sm font-medium text-muted-foreground">{eyebrow}</p>}
        <h1 className="text-[28px] font-bold leading-tight tracking-tight sm:text-3xl">{title}</h1>
        {description && <p className="mt-1 text-[15px] text-muted-foreground">{description}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {action}
        {showThemeToggle && <ThemeToggle />}
      </div>
    </header>
  );
}
