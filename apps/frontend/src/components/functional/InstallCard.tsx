"use client";

import { Download, Share, Smartphone, SquarePlus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useInstallPrompt } from "@/hooks/useInstallPrompt";

/** "Add Savora to your home screen": native prompt where supported, steps on iOS. */
export function InstallCard() {
  const { standalone, canPrompt, showIosHint, install } = useInstallPrompt();
  if (standalone || (!canPrompt && !showIosHint)) return null;
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center gap-3">
        <span className="grid size-11 place-items-center rounded-2xl bg-primary-soft text-primary-soft-foreground">
          <Smartphone className="size-5" aria-hidden />
        </span>
        <div>
          <h2 className="font-semibold">Install Savora</h2>
          <p className="text-sm text-muted-foreground">Open it from your home screen like an app.</p>
        </div>
      </div>
      {canPrompt ? (
        <Button onClick={() => void install()} icon={<Download className="size-4" aria-hidden />}>
          Add to home screen
        </Button>
      ) : (
        <ol className="flex flex-col gap-1.5 text-sm text-muted-foreground">
          <li className="flex items-center gap-2">
            1. Tap <Share className="size-4 text-foreground" aria-label="Share" /> in Safari
          </li>
          <li className="flex items-center gap-2">
            2. Choose <SquarePlus className="size-4 text-foreground" aria-hidden /> Add to Home Screen
          </li>
        </ol>
      )}
    </Card>
  );
}
