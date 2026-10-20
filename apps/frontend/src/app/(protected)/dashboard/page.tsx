import { WeeklyPlannerView } from "@/core/private/MealPlanning/components/WeeklyPlannerView";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ swapSlot?: string }>;
}) {
  const params = await searchParams;
  return <WeeklyPlannerView initialSwapSlot={params.swapSlot ?? null} />;
}
