import type { Metadata } from "next";
import { DiscoverChat } from "@/core/private/Craving/components/DiscoverChat";

export const metadata: Metadata = { title: "Discover" };

export default function DiscoverPage() {
  return <DiscoverChat />;
}
