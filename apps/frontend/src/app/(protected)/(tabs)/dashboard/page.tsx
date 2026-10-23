import type { Metadata } from "next";
import { HomeView } from "@/core/private/MealPlanning/components/HomeView";

export const metadata: Metadata = { title: "Home" };

export default function DashboardPage() {
  return <HomeView />;
}
