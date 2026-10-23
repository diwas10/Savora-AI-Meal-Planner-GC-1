import type { Metadata } from "next";
import { Suspense } from "react";
import { MyPlanView } from "@/core/private/MealPlanning/components/MyPlanView";

export const metadata: Metadata = { title: "My Plan" };

export default function MealPlansPage() {
  return (
    <Suspense>
      <MyPlanView />
    </Suspense>
  );
}
