"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { PageHeader } from "@/components/functional/PageHeader";
import { Button, LinkButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorSummary } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { InlineAlert } from "@/components/ui/States";
import { ApiError } from "@/lib/api-request";
import { profileFormSchema, toFormValues, toUpsertRequest, type ProfileFormValues } from "../schema/profile.schema";
import { useProfileQuery, useUpsertProfileMutation } from "../service/profile.query";
import { AboutYouSection, FoodSection, HealthSection } from "./ProfileSections";

export function ProfileEditSkeleton() {
  return (
    <div className="flex flex-col gap-8 pb-8" aria-hidden>
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-32" />
        <Card className="flex flex-col gap-4 p-5">
          <Skeleton className="h-10 w-full rounded-xl" />
          <div className="grid grid-cols-2 gap-4">
            <Skeleton className="h-10 rounded-xl" />
            <Skeleton className="h-10 rounded-xl" />
          </div>
          <Skeleton className="h-10 w-full rounded-xl" />
        </Card>
      </div>
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-40" />
        <Card className="flex flex-col gap-4 p-5">
          <Skeleton className="h-10 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </Card>
      </div>
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-48" />
        <Card className="flex flex-col gap-4 p-5">
          <Skeleton className="h-10 w-full rounded-xl" />
          <Skeleton className="h-10 w-full rounded-xl" />
        </Card>
      </div>
      <Skeleton className="h-12 w-full rounded-2xl" />
    </div>
  );
}

export function ProfileEditView() {
  const router = useRouter();
  const profile = useProfileQuery();
  const upsert = useUpsertProfileMutation();
  const [serverErrors, setServerErrors] = useState<string[]>([]);
  const before = profile.data?.profile.version;
  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    defaultValues: toFormValues(profile.data?.profile),
    values: profile.data?.profile ? toFormValues(profile.data.profile) : undefined,
    mode: "onTouched",
  });

  const save = form.handleSubmit(async (values) => {
    setServerErrors([]);
    try {
      const saved = await upsert.mutateAsync(toUpsertRequest(values));
      if (saved.profile.version === before) router.replace("/profile");
    } catch (error) {
      setServerErrors(
        error instanceof ApiError
          ? Object.values(error.fieldErrors).flat().concat(Object.keys(error.fieldErrors).length ? [] : [error.message])
          : ["We couldn't save your profile. Your changes are kept; please try again."],
      );
    }
  });

  const changed = upsert.data && before !== undefined && upsert.data.profile.version !== before;
  const errors = Object.values(form.formState.errors)
    .map((e) => e?.message)
    .filter((m): m is string => Boolean(m));

  return (
    <>
      <PageHeader
        title="Edit profile"
        description="Targets are recalculated only when something relevant changes."
        action={
          <LinkButton href="/profile" variant="ghost" size="sm" icon={<ArrowLeft className="size-4" aria-hidden />}>
            Back
          </LinkButton>
        }
      />
      {profile.isPending ? (
        <ProfileEditSkeleton />
      ) : changed ? (
        <Card className="flex flex-col gap-4 p-5">
          <InlineAlert tone="success" icon={<Check className="size-4" aria-hidden />} title={`Saved as profile version ${upsert.data.profile.version}`}>
            Your targets were recalculated. Your current plan was made for the earlier profile, so
            generate a new plan to apply the changes (swaps need a new plan too).
          </InlineAlert>
          <div className="flex flex-wrap gap-2">
            <LinkButton href="/meal-plans">Go to My Plan</LinkButton>
            <LinkButton href="/profile" variant="secondary">
              View profile
            </LinkButton>
          </div>
        </Card>
      ) : (
        <form noValidate onSubmit={(e) => void save(e)} className="flex flex-col gap-8 pb-8">
          {form.formState.submitCount > 0 && <ErrorSummary errors={errors} />}
          <ErrorSummary errors={serverErrors} title="We couldn't save that" />
          <section aria-labelledby="edit-about" className="flex flex-col gap-4">
            <h2 id="edit-about" className="text-lg font-semibold">About you</h2>
            <AboutYouSection form={form} />
          </section>
          <section aria-labelledby="edit-food" className="flex flex-col gap-4">
            <h2 id="edit-food" className="text-lg font-semibold">Food and culture</h2>
            <FoodSection form={form} />
          </section>
          <section aria-labelledby="edit-health" className="flex flex-col gap-4">
            <h2 id="edit-health" className="text-lg font-semibold">Allergies and health</h2>
            <HealthSection form={form} />
          </section>
          <Button type="submit" size="lg" block loading={upsert.isPending}>
            Save changes
          </Button>
        </form>
      )}
    </>
  );
}
