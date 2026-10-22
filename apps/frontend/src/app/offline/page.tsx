import type { Metadata } from "next";
import { WifiOff } from "lucide-react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/Button";

export const metadata: Metadata = { title: "Offline" };

/** Served by the service worker when a page is requested without a connection. */
export default function OfflinePage() {
  return (
    <main className="grid min-h-dvh place-items-center px-6 text-center">
      <div className="flex max-w-sm flex-col items-center">
        <span className="mb-5 grid size-16 place-items-center rounded-3xl bg-warning-soft text-warning-foreground">
          <WifiOff className="size-8" aria-hidden />
        </span>
        <h1 className="text-2xl font-bold tracking-tight">You&apos;re offline</h1>
        <p className="mt-2 text-[15px] text-muted-foreground">
          Pages you have opened before still work. Generating plans, swapping meals and Discover
          need a connection.
        </p>
        <Link href="/dashboard" className={buttonVariants({ className: "mt-6" })}>
          Try again
        </Link>
      </div>
    </main>
  );
}
