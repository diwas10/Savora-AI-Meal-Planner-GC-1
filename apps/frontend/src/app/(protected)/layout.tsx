import type { ReactNode } from "react";
import { ProtectedShell } from "@/components/functional/ProtectedShell";

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return <ProtectedShell>{children}</ProtectedShell>;
}
