import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "skeleton animate-pulse rounded-2xl bg-surface-muted",
        className,
      )}
    />
  );
}
