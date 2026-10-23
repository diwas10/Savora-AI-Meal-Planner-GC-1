import type { Metadata } from "next";
import { ProfileEditView } from "@/core/private/UserProfile/components/ProfileEditView";

export const metadata: Metadata = { title: "Edit profile" };

export default function ProfileEditPage() {
  return <ProfileEditView />;
}
