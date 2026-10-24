import { CircleAlert } from "lucide-react";
import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const controlClass =
  "w-full rounded-2xl bg-surface/85 backdrop-blur-sm px-4 text-[15px] text-foreground ring-1 ring-border placeholder:text-subtle-foreground transition-shadow focus:outline-none focus:ring-2 focus:ring-ring aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-danger";

interface FieldProps {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}

/** Visible label, optional hint and an inline error tied to the control by id. */
export function Field({ id, label, hint, error, children, className }: FieldProps) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium text-foreground">
        {label}
      </label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} role="alert" className="flex items-center gap-1 text-xs font-medium text-danger">
          <CircleAlert className="size-3.5" aria-hidden />
          {error}
        </p>
      )}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(controlClass, "h-12", className)} {...props} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return <textarea ref={ref} className={cn(controlClass, "min-h-24 py-3", className)} {...props} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...props }, ref) {
    return (
      <select ref={ref} className={cn(controlClass, "h-12 appearance-none pr-10", className)} {...props}>
        {children}
      </select>
    );
  },
);

/** Accessible error summary for a form: lists every field error, focusable. */
export function ErrorSummary({ errors, title = "Please fix the following" }: { errors: string[]; title?: string }) {
  if (errors.length === 0) return null;
  return (
    <div role="alert" tabIndex={-1} className="rounded-2xl bg-danger-soft p-4 text-sm text-danger-foreground">
      <p className="font-semibold">{title}</p>
      <ul className="mt-1 list-disc pl-5">
        {errors.map((e) => (
          <li key={e}>{e}</li>
        ))}
      </ul>
    </div>
  );
}

interface SegmentedProps<T extends string> {
  name: string;
  label: string;
  value: T;
  options: ReadonlyArray<{ value: T; label: string; hint?: string }>;
  onChange: (value: T) => void;
  columns?: 2 | 3;
}

/** A radio group styled as segments (native radios: keyboard arrows work). */
export function Segmented<T extends string>({ name, label, value, options, onChange, columns = 3 }: SegmentedProps<T>) {
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1.5 text-sm font-medium text-foreground">{label}</legend>
      <div className={cn("grid gap-2", columns === 2 ? "grid-cols-2" : "grid-cols-3")}>
        {options.map((o) => {
          const checked = o.value === value;
          return (
            <label
              key={o.value}
              className={cn(
                "flex min-h-12 cursor-pointer flex-col items-center justify-center rounded-2xl px-2 py-2 text-center text-sm font-medium ring-1 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                checked
                  ? "bg-primary-soft text-primary-soft-foreground ring-primary"
                  : "bg-surface text-foreground ring-border hover:bg-surface-muted",
              )}
            >
              <input
                type="radio"
                name={name}
                value={o.value}
                checked={checked}
                onChange={() => onChange(o.value)}
                className="sr-only"
              />
              <span>{o.label}</span>
              {o.hint && <span className="text-[11px] font-normal text-muted-foreground">{o.hint}</span>}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
