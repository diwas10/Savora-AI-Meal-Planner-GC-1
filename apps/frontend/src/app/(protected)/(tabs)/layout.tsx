import type { ReactNode } from "react";
import { AppShell } from "@/components/functional/AppShell";

export default function TabsLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
