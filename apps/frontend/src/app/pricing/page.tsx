import type { Metadata } from "next";
import { PricingView } from "@/core/public/Pricing/components/PricingView";

export const metadata: Metadata = {
  title: "Pricing & Plans",
  description:
    "Transparent pricing for Savora. Choose Free at S$0 or Premium at S$6.90/month for advanced preferences, more planning, and substitution features.",
};

export default function PricingPage() {
  return <PricingView />;
}
