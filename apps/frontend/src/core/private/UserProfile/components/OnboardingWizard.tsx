"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, PartyPopper } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm, type FieldPath } from "react-hook-form";
import { Wordmark } from "@/components/functional/Brand";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorSummary } from "@/components/ui/Field";
import { GeneratePanel } from "@/core/private/MealPlanning/components/GeneratePanel";
import { ApiError } from "@/lib/api-request";
import { gentle } from "@/lib/motion";
import { profileFormSchema, toFormValues, toUpsertRequest, type ProfileFormValues } from "../schema/profile.schema";
import { useProfileQuery, useUpsertProfileMutation } from "../service/profile.query";
import { AboutYouSection, FoodSection, HealthSection } from "./ProfileSections";
import { SeedPicker } from "./SeedPicker";
import { TargetsCard } from "./TargetsCard";
import { ThemeToggle } from "@/core/common/theme/ThemeToggle";

type StepId = "about" | "food" | "health" | "targets" | "seeds" | "done";

const STEPS: Array<{ id: StepId; title: string; description: string; fields?: FieldPath<ProfileFormValues>[] }> = [
  { id: "about", title: "About you", description: "Used only to estimate your daily energy and protein.", fields: ["ageYears", "sex", "heightCm", "weightKg", "activity", "goal"] },
  { id: "food", title: "Food and culture", description: "What you eat and how strictly to follow it.", fields: ["diet", "cuisinePolicy", "cuisines", "excludedIngredients"] },
  { id: "health", title: "Allergies and health", description: "Allergies are always applied, everywhere.", fields: ["allergies", "allergiesConfirmed", "conditions"] },
  { id: "targets", title: "Your estimated targets", description: "Review them before Savora plans your week." },
  { id: "seeds", title: "Dishes you like", description: "Pick 3 to 5 so recommendations start with your taste." },
  { id: "done", title: "You're all set", description: "Generate your first 7-day plan." },
];

export function OnboardingWizard() {
  const router = useRouter();
  const profile = useProfileQuery();
  const upsert = useUpsertProfileMutation();
  const existing = profile.data;
  const [step, setStep] = useState<number>(() => (existing?.needsSeedPicks ? 4 : 0));
  const [direction, setDirection] = useState(1);
  const [serverErrors, setServerErrors] = useState<string[]>([]);

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    defaultValues: toFormValues(existing?.profile),
    mode: "onTouched",
  });

  const current = STEPS[step] ?? STEPS[0];
  const go = (next: number) => {
    setDirection(next > step ? 1 : -1);
    setStep(next);
    window.scrollTo({ top: 0 });
  };

  const nextFromForm = async () => {
    const ok = await form.trigger(current.fields, { shouldFocus: true });
    if (!ok) return;
    if (current.id !== "health") {
      go(step + 1);
      return;
    }
    setServerErrors([]);
    try {
      await upsert.mutateAsync(toUpsertRequest(form.getValues()));
      go(step + 1);
    } catch (error) {
      if (error instanceof ApiError) {
        setServerErrors(Object.values(error.fieldErrors).flat().length ? Object.values(error.fieldErrors).flat() : [error.message]);
      } else {
        setServerErrors(["We couldn't save your profile. Your answers are kept; please try again."]);
      }
    }
  };

  const stepErrors = Object.entries(form.formState.errors)
    .filter(([key]) => current.fields?.includes(key as FieldPath<ProfileFormValues>))
    .map(([, e]) => e?.message)
    .filter((m): m is string => Boolean(m));

  const targets = upsert.data ?? existing;

  if (profile.isPending) {
    return <OnboardingSkeleton />;
  }

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-xl flex-col px-5 pb-10 pt-safe">
      <header className="sticky top-0 z-10 -mx-5 bg-background/85 px-5 pb-3 pt-4 backdrop-blur-md">
        <div className="flex h-11 items-center justify-between">
          {step > 0 && step < 5 && current.id !== "seeds" ? (
            <Button variant="ghost" size="icon" onClick={() => go(step - 1)} aria-label="Back">
              <ArrowLeft className="size-5" aria-hidden />
            </Button>
          ) : (
            <Wordmark />
          )}
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium tabular-nums text-muted-foreground">
              Step {step + 1} of {STEPS.length}
            </span>
            <ThemeToggle />
          </div>
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-pill bg-surface-sunken" role="progressbar" aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={step + 1} aria-label="Onboarding progress">
          <motion.div className="h-full rounded-pill bg-primary" initial={false} animate={{ width: `${((step + 1) / STEPS.length) * 100}%` }} transition={gentle} />
        </div>
      </header>

      <AnimatePresence mode="wait" custom={direction} initial={false}>
        <motion.section
          key={current.id}
          custom={direction}
          initial={{ opacity: 0, x: 24 * direction }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -24 * direction }}
          transition={gentle}
          aria-labelledby="step-title"
          className="flex flex-1 flex-col pt-4"
        >
          <h1 id="step-title" className="text-[28px] font-bold leading-tight tracking-tight">
            {current.title}
          </h1>
          <p className="mb-6 mt-1 text-[15px] text-muted-foreground">{current.description}</p>

          {current.fields && (
            <form
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                void nextFromForm();
              }}
              className="flex flex-1 flex-col gap-6"
            >
              {form.formState.submitCount > 0 && <ErrorSummary errors={stepErrors} />}
              <ErrorSummary errors={serverErrors} title="We couldn't save that" />
              {current.id === "about" && <AboutYouSection form={form} />}
              {current.id === "food" && <FoodSection form={form} />}
              {current.id === "health" && <HealthSection form={form} />}
              <div className="mt-auto pt-4">
                <Button type="submit" size="lg" block loading={upsert.isPending} icon={<ArrowRight className="size-5" aria-hidden />}>
                  {current.id === "health" ? "Calculate my targets" : "Continue"}
                </Button>
              </div>
            </form>
          )}

          {current.id === "targets" && targets && (
            <div className="flex flex-1 flex-col gap-6">
              <TargetsCard targets={targets.targets} profileVersion={targets.profile.version} profile={targets.profile} />
              <div className="mt-auto flex flex-col gap-2 pt-2">
                <Button size="lg" block onClick={() => go(4)} icon={<ArrowRight className="size-5" aria-hidden />}>
                  Looks good
                </Button>
                <Button variant="ghost" block onClick={() => go(0)}>
                  Change my answers
                </Button>
              </div>
            </div>
          )}

          {current.id === "seeds" && <SeedPicker initial={existing?.profile.seedRecipeIds ?? []} onDone={() => go(5)} />}

          {current.id === "done" && (
            <div className="flex flex-col gap-6">
              <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={gentle} className="mx-auto grid size-20 place-items-center rounded-[28px] bg-accent-soft text-accent-soft-foreground">
                <PartyPopper className="size-10" aria-hidden />
              </motion.div>
              <GeneratePanel compact title="Your first week" onStarted={() => router.replace("/dashboard")} />
              <Button variant="ghost" block onClick={() => router.replace("/dashboard")}>
                Maybe later
              </Button>
            </div>
          )}
        </motion.section>
      </AnimatePresence>
    </div>
  );
}

export function OnboardingSkeleton() {
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-xl flex-col px-5 pb-10 pt-safe" aria-hidden>
      <header className="sticky top-0 z-10 -mx-5 bg-background/85 px-5 pb-3 pt-4 backdrop-blur-md">
        <div className="flex h-11 items-center justify-between">
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-5 w-20 rounded-pill" />
        </div>
        <Skeleton className="mt-3 h-1.5 w-full rounded-pill" />
      </header>
      <div className="flex flex-1 flex-col pt-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-72" />
        <Card className="flex flex-col gap-4 p-5">
          <Skeleton className="h-10 w-full rounded-xl" />
          <Skeleton className="h-10 w-full rounded-xl" />
          <Skeleton className="h-10 w-full rounded-xl" />
        </Card>
        <Skeleton className="mt-4 h-12 w-full rounded-2xl" />
      </div>
    </div>
  );
}
