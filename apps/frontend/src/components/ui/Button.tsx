import { cva, type VariantProps } from "class-variance-authority";
import { LoaderCircle } from "lucide-react";
import Link from "next/link";
import type { ButtonHTMLAttributes, ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-semibold transition-[background-color,color,box-shadow,transform] duration-150 active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2",
  {
    variants: {
      variant: {
        primary:
          "bg-primary text-primary-foreground shadow-glow hover:bg-primary-strong",
        secondary:
          "bg-surface text-foreground ring-1 ring-border shadow-card hover:bg-surface-muted",
        subtle: "bg-primary-soft text-primary-soft-foreground hover:bg-primary-soft/80",
        ghost: "text-foreground hover:bg-surface-muted",
        destructive: "bg-danger-soft text-danger-foreground hover:bg-danger-soft/80",
        accent: "bg-accent text-accent-foreground hover:bg-accent/90",
      },
      size: {
        sm: "h-9 rounded-pill px-3.5 text-sm",
        md: "h-11 rounded-pill px-5 text-[15px]",
        lg: "h-14 rounded-pill px-7 text-base",
        icon: "size-11 rounded-pill",
      },
      block: { true: "w-full" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type ButtonVariants = VariantProps<typeof buttonVariants>;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, ButtonVariants {
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({
  className,
  variant,
  size,
  block,
  loading = false,
  icon,
  children,
  disabled,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(buttonVariants({ variant, size, block }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

interface LinkButtonProps extends ComponentProps<typeof Link>, ButtonVariants {
  icon?: ReactNode;
}

export function LinkButton({ className, variant, size, block, icon, children, ...props }: LinkButtonProps) {
  return (
    <Link className={cn(buttonVariants({ variant, size, block }), className)} {...props}>
      {icon}
      {children}
    </Link>
  );
}
