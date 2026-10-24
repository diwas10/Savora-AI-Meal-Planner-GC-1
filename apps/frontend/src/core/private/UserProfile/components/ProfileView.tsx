"use client";

import {
  CalendarDays,
  ChevronRight,
  CreditCard,
  Heart,
  Laptop,
  LogOut,
  Moon,
  Pencil,
  ShieldAlert,
  Sun,
  UtensilsCrossed,
} from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { InstallCard } from "@/components/functional/InstallCard";
import { PageHeader } from "@/components/functional/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button, LinkButton } from "@/components/ui/Button";
import { Card, SectionTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useTheme } from "@/core/common/theme/ThemeContext";
import { useCurrentUserQuery, useLogout } from "@/core/public/Auth/service/auth.query";
import { useOnline } from "@/hooks/useOnline";
import { fadeUp, stagger } from "@/lib/motion";
import { ACTIVITY_OPTIONS, CONDITION_OPTIONS } from "../schema/profile.schema";
import { useProfileQuery } from "../service/profile.query";
import { FavouriteDishesSheet } from "./SeedPicker";
import { TargetsCard } from "./TargetsCard";

const GOAL = { LOSE: "Lose weight", MAINTAIN: "Maintain weight", GAIN: "Gain weight" } as const;
const POLICY = { MIXED: "Any cuisine", MAJORITY: "Mostly my cuisines", STRICT: "Only my cuisines" } as const;

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-right text-sm font-medium">{children}</dd>
    </div>
  );
}

function List({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <span className="font-normal text-muted-foreground">{empty}</span>;
  return (
    <span className="flex flex-wrap justify-end gap-1">
      {items.map((i) => (
        <Badge key={i}>{i}</Badge>
      ))}
    </span>
  );
}

export function ProfileView() {
  const router = useRouter();
  const user = useCurrentUserQuery();
  const profile = useProfileQuery();
  const logout = useLogout();
  const online = useOnline();
  const { theme, setTheme } = useTheme();
  const [seedsOpen, setSeedsOpen] = useState(false);

  const signOut = () => {
    logout();
    router.replace("/login");
  };

  const p = profile.data?.profile;
  return (
    <>
      <PageHeader title="Profile" description={user.data?.email} />
      {profile.isPending ? (
        <ProfileSkeleton />
      ) : profile.isError || !p || !profile.data ? (
        <Card>
          <ErrorState message="We couldn't load your profile." offline={!online} onRetry={() => void profile.refetch()} />
        </Card>
      ) : (
        <motion.div variants={stagger} initial="hidden" animate="show" className="flex flex-col gap-6">
          <motion.div variants={fadeUp} className="flex items-center gap-4">
            <span className="grid size-16 place-items-center rounded-[22px] bg-gradient-to-br from-hero-from via-hero-via to-hero-to text-2xl font-bold text-hero-ink shadow-glow">
              {user.data?.displayName.charAt(0).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-lg font-semibold">{user.data?.displayName}</p>
              <p className="text-sm text-muted-foreground">Profile version {p.version}</p>
            </div>
            <LinkButton href="/profile/edit" variant="secondary" size="sm" icon={<Pencil className="size-4" aria-hidden />}>
              Edit
            </LinkButton>
          </motion.div>

          <motion.section variants={fadeUp} aria-labelledby="targets-title">
            <SectionTitle title="Daily targets" />
            <h2 id="targets-title" className="sr-only">
              Daily targets
            </h2>
            <TargetsCard targets={profile.data.targets} profileVersion={p.version} profile={p} />
          </motion.section>

          <motion.section variants={fadeUp}>
            <SectionTitle title="About you" />
            <Card className="px-5">
              <dl className="divide-y divide-border">
                <Row label="Age">{p.ageYears} years</Row>
                <Row label="Height · weight">
                  {p.heightCm} cm · {p.weightKg} kg
                </Row>
                <Row label="Activity">{ACTIVITY_OPTIONS.find((a) => a.value === p.activity)?.label}</Row>
                <Row label="Goal">{GOAL[p.goal]}</Row>
              </dl>
            </Card>
          </motion.section>

          <motion.section variants={fadeUp}>
            <SectionTitle title="Food and health" />
            <Card className="px-5">
              <dl className="divide-y divide-border">
                <Row label="Diet">{p.diet ? p.diet.charAt(0) + p.diet.slice(1).toLowerCase() : "No rule"}</Row>
                <Row label="Cuisines">
                  <span className="block text-xs font-normal text-muted-foreground">{POLICY[p.cuisinePolicy]}</span>
                  <List items={p.cuisines} empty="Any" />
                </Row>
                <Row label="Leave out">
                  <List items={p.excludedIngredients} empty="Nothing" />
                </Row>
                <Row label="Allergies">
                  {p.allergies.length > 0 ? (
                    <span className="flex flex-col items-end gap-1">
                      <List items={p.allergies} empty="" />
                      <span className="flex items-center gap-1 text-xs font-normal text-success">
                        <ShieldAlert className="size-3.5" aria-hidden /> Confirmed, always applied
                      </span>
                    </span>
                  ) : (
                    <span className="font-normal text-muted-foreground">None</span>
                  )}
                </Row>
                <Row label="Health conditions">
                  <List items={p.conditions.map((c) => CONDITION_OPTIONS.find((o) => o.value === c)?.label ?? c)} empty="None" />
                </Row>
              </dl>
            </Card>
          </motion.section>

          {/* Theme switcher */}
          <motion.section variants={fadeUp} className="flex flex-col gap-3">
            <SectionTitle title="Appearance" />
            <Card className="flex items-center justify-between p-4">
              <div>
                <p className="text-sm font-medium text-foreground">Theme</p>
                <p className="text-xs text-muted-foreground">Choose light, dark, or system mode</p>
              </div>
              <div className="flex items-center gap-1 rounded-pill bg-surface-muted p-1 ring-1 ring-border">
                <ThemeButton
                  active={theme === "light"}
                  icon={<Sun className="size-4" aria-hidden />}
                  label="Light"
                  onClick={() => setTheme("light")}
                />
                <ThemeButton
                  active={theme === "dark"}
                  icon={<Moon className="size-4" aria-hidden />}
                  label="Dark"
                  onClick={() => setTheme("dark")}
                />
                <ThemeButton
                  active={theme === "system"}
                  icon={<Laptop className="size-4" aria-hidden />}
                  label="System"
                  onClick={() => setTheme("system")}
                />
              </div>
            </Card>
          </motion.section>

          <motion.section variants={fadeUp} className="flex flex-col gap-3">
            <SectionTitle title="Your Savora" />
            <ProfileLink icon={<Heart className="size-5" aria-hidden />} title="Favourite dishes" detail={`${p.seedRecipeIds.length} picked`} onClick={() => setSeedsOpen(true)} />
            <ProfileLink icon={<CalendarDays className="size-5" aria-hidden />} title="Saved plans" detail="Every version is kept" href="/meal-plans" />
            <ProfileLink icon={<UtensilsCrossed className="size-5" aria-hidden />} title="Discover dishes" detail="Ask for a craving" href="/discover" />
            <ProfileLink icon={<CreditCard className="size-5" aria-hidden />} title="Pricing & plans" detail="Free (S$0) · Premium (S$6.90/mo)" href="/pricing" />
          </motion.section>

          <motion.div variants={fadeUp}>
            <InstallCard />
          </motion.div>

          <motion.div variants={fadeUp} className="pt-2">
            <Button variant="destructive" size="lg" block onClick={signOut} icon={<LogOut className="size-5" aria-hidden />}>
              Log out
            </Button>
            <p className="mt-3 text-center text-xs text-muted-foreground">
              Savora GC1 · results use stand-in rules, not verified clinical advice
            </p>
          </motion.div>
        </motion.div>
      )}

      {p && (
        <FavouriteDishesSheet
          open={seedsOpen}
          onOpenChange={setSeedsOpen}
          initial={p.seedRecipeIds}
        />
      )}
    </>
  );
}

function ThemeButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-pill px-3 py-1.5 text-xs font-semibold transition ${
        active
          ? "bg-surface/90 backdrop-blur-sm text-foreground shadow-sm ring-1 ring-border"
          : "text-muted-foreground hover:text-foreground"
      }`}
      aria-pressed={active}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

function ProfileLink({
  icon,
  title,
  detail,
  href,
  onClick,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
  href?: string;
  onClick?: () => void;
}) {
  const body = (
    <>
      <span className="grid size-11 place-items-center rounded-2xl bg-primary-soft text-primary-soft-foreground">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">{title}</span>
        <span className="block text-sm text-muted-foreground">{detail}</span>
      </span>
      <ChevronRight className="size-5 text-subtle-foreground" aria-hidden />
    </>
  );
  const className = "flex w-full items-center gap-3 rounded-card bg-surface/80 backdrop-blur-md p-3.5 text-left shadow-card ring-1 ring-border/70 transition-colors hover:bg-surface-muted/90";
  return href ? (
    <Link href={href} className={className}>
      {body}
    </Link>
  ) : (
    <button type="button" onClick={onClick} className={className}>
      {body}
    </button>
  );
}

export function ProfileSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-hidden>
      <div className="flex items-center gap-4">
        <Skeleton className="size-16 rounded-[22px]" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-4 w-24" />
        </div>
        <Skeleton className="h-9 w-16 rounded-pill" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-48 rounded-card" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-40 rounded-card" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-36 rounded-card" />
      </div>
    </div>
  );
}
