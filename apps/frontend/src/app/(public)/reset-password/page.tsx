import type { Metadata } from "next";
import { Suspense } from "react";
import { ResetPasswordForm } from "@/core/public/Auth/components/ResetPasswordForm";

export const metadata: Metadata = { title: "Choose a new password" };

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
