"use client";

import { X } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

interface TagInputProps {
  id: string;
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  suggestions?: string[];
  invalid?: boolean;
  describedBy?: string;
}

/** Type and press Enter (or comma) to add; each tag has its own remove button. */
export function TagInput({ id, value, onChange, placeholder, suggestions = [], invalid, describedBy }: TagInputProps) {
  const [draft, setDraft] = useState("");
  const add = (raw: string) => {
    const tag = raw.trim().replace(/,$/, "").trim().toLowerCase();
    if (tag && !value.includes(tag)) onChange([...value, tag]);
    setDraft("");
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };
  const open = suggestions.filter((s) => !value.includes(s));
  return (
    <div className="flex flex-col gap-2">
      <div
        className={cn(
          "flex min-h-12 flex-wrap items-center gap-1.5 rounded-2xl bg-surface p-1.5 ring-1 ring-border focus-within:ring-2 focus-within:ring-ring",
          invalid && "ring-2 ring-danger",
        )}
      >
        {value.map((tag) => (
          <span key={tag} className="inline-flex h-8 items-center gap-1 rounded-pill bg-primary-soft pl-3 pr-1 text-sm font-medium text-primary-soft-foreground">
            {tag}
            <button
              type="button"
              onClick={() => onChange(value.filter((t) => t !== tag))}
              className="grid size-6 place-items-center rounded-pill hover:bg-primary/15"
              aria-label={`Remove ${tag}`}
            >
              <X className="size-3.5" aria-hidden />
            </button>
          </span>
        ))}
        <input
          id={id}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => draft && add(draft)}
          placeholder={value.length ? "" : placeholder}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className="h-9 min-w-32 flex-1 bg-transparent px-2 text-[15px] placeholder:text-subtle-foreground focus:outline-none"
        />
      </div>
      {open.length > 0 && (
        <div className="flex flex-wrap gap-1.5" aria-label="Common choices">
          {open.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => add(s)}
              className="h-8 rounded-pill bg-surface-muted px-3 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
