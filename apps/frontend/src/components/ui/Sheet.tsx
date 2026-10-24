"use client";

import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Drawer } from "vaul";
import { cn } from "@/lib/utils";

interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

/**
 * Bottom sheet (Radix dialog via vaul): focus is trapped and restored, Escape and the
 * close button dismiss it, the body scrolls inside the sheet, drag-to-dismiss on touch.
 */
export function Sheet({ open, onOpenChange, title, description, children, footer, className }: SheetProps) {
  return (
    <Drawer.Root open={open} onOpenChange={onOpenChange} shouldScaleBackground={false}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-50 bg-scrim/60 backdrop-blur-md transition-opacity" />
        <Drawer.Content
          className={cn(
            "glass fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[92dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-sheet bg-glass-strong/95 backdrop-blur-2xl outline-none sm:bottom-4 sm:max-h-[88dvh] sm:rounded-sheet",
            className,
          )}
        >
          <Drawer.Handle className="mx-auto mt-2.5 h-1.5 w-11 shrink-0 rounded-pill bg-border-strong" />
          <div className="flex items-start justify-between gap-3 px-5 pb-2 pt-3">
            <div className="min-w-0">
              <Drawer.Title className="text-lg font-semibold tracking-tight">{title}</Drawer.Title>
              {description ? (
                <Drawer.Description className="mt-0.5 text-sm text-muted-foreground">{description}</Drawer.Description>
              ) : (
                <Drawer.Description className="sr-only">{title}</Drawer.Description>
              )}
            </div>
            <Drawer.Close
              className="grid size-11 shrink-0 place-items-center rounded-pill bg-surface-muted/80 backdrop-blur-sm text-muted-foreground transition-colors hover:text-foreground"
              aria-label="Close"
            >
              <X className="size-5" aria-hidden />
            </Drawer.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-5">{children}</div>
          {footer && <div className="border-t border-border/70 bg-surface/75 px-5 py-4 backdrop-blur-md pb-safe">{footer}</div>}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
