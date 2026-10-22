import type { Metadata } from "next";
import { ProfileView } from "@/core/private/UserProfile/components/ProfileView";

export const metadata: Metadata = { title: "Profile" };

export default function ProfilePage() {
  return <ProfileView />;
}
