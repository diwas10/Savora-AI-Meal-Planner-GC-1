import type { Metadata } from "next";
import { OnboardingWizard } from "@/core/private/UserProfile/components/OnboardingWizard";

export const metadata: Metadata = { title: "Set up your profile" };

export default function OnboardingPage() {
  return <OnboardingWizard />;
}
