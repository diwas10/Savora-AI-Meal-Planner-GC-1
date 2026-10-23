import type { Metadata } from "next";
import { RegisterForm } from "@/core/public/Auth/components/RegisterForm";

export const metadata: Metadata = { title: "Create account" };

export default function RegisterPage() {
  return <RegisterForm />;
}
