"use client";

import { Laptop, Moon, Sun } from "lucide-react";
import type { ReactNode } from "react";
import { useTheme, type Theme } from "@/core/common/theme/ThemeContext";
import { cn } from "@/lib/utils";

interface ThemeToggleProps {
  className?: string;
  onHero?: boolean;
  variant?: "button" | "segmented";
}

const NEXT_THEME: Record<Theme, Theme> = {
  light: "dark",
  dark: "system",
  system: "light",
};

const THEME_LABELS: Record<Theme, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

export function ThemeToggle({
  className,
  onHero = false,
  variant = "button",
}: ThemeToggleProps) {
  const { theme, setTheme } = useTheme();

  const cycleTheme = () => {
    setTheme(NEXT_THEME[theme]);
  };

  if (variant === "segmented") {
    return (
      <div
        className={cn(
          "flex items-center gap-1 rounded-pill p-1 ring-1",
          onHero
            ? "bg-hero-ink/10 ring-hero-ink/20"
            : "bg-surface-muted/80 backdrop-blur-sm ring-border",
          className,
        )}
      >
        <ThemeSegment
          active={theme === "light"}
          icon={<Sun className="size-3.5" aria-hidden />}
          label="Light"
          onHero={onHero}
          onClick={() => setTheme("light")}
        />
        <ThemeSegment
          active={theme === "dark"}
          icon={<Moon className="size-3.5" aria-hidden />}
          label="Dark"
          onHero={onHero}
          onClick={() => setTheme("dark")}
        />
        <ThemeSegment
          active={theme === "system"}
          icon={<Laptop className="size-3.5" aria-hidden />}
          label="System"
          onHero={onHero}
          onClick={() => setTheme("system")}
        />
      </div>
    );
  }

  const nextLabel = THEME_LABELS[NEXT_THEME[theme]];

  return (
    <button
      type="button"
      onClick={cycleTheme}
      className={cn(
        "relative flex size-9 shrink-0 items-center justify-center rounded-full transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        onHero
          ? "bg-hero-ink/15 text-hero-ink hover:bg-hero-ink/25 ring-1 ring-hero-ink/30"
          : "bg-surface/85 backdrop-blur-sm text-foreground shadow-sm ring-1 ring-border/80 hover:bg-surface-muted/90 hover:text-primary",
        className,
      )}
      aria-label={`Current theme: ${THEME_LABELS[theme]}. Click to switch to ${nextLabel}.`}
      title={`Theme: ${THEME_LABELS[theme]} (click for ${nextLabel})`}
    >
      {theme === "light" && <Sun className="size-4 text-amber-500 transition-transform hover:rotate-45" aria-hidden />}
      {theme === "dark" && <Moon className="size-4 text-sky-400 transition-transform hover:-rotate-12" aria-hidden />}
      {theme === "system" && <Laptop className="size-4 text-primary transition-transform" aria-hidden />}
      <span className="sr-only">Toggle theme (currently {THEME_LABELS[theme]})</span>
    </button>
  );
}

function ThemeSegment({
  active,
  icon,
  label,
  onHero,
  onClick,
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onHero: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 rounded-pill px-2.5 py-1 text-xs font-semibold transition",
        active
          ? onHero
            ? "bg-hero-ink text-hero-from shadow-sm"
            : "bg-surface text-foreground shadow-sm ring-1 ring-border"
          : onHero
            ? "text-hero-ink/75 hover:text-hero-ink"
            : "text-muted-foreground hover:text-foreground",
      )}
      aria-pressed={active}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}
