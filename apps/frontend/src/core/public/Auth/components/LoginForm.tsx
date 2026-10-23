"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { InlineAlert } from "@/components/ui/States";
import { ApiError } from "@/lib/api-request";
import { loginSchema, type LoginFormValues } from "../schema/auth.schema";
import { useLoginMutation } from "../service/auth.query";
import { AuthLayout } from "./AuthLayout";
import { PasswordInput } from "./PasswordInput";

function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const login = useLoginMutation();
  const form = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });
  const { errors } = form.formState;

  const submit = form.handleSubmit(async (values) => {
    await login.mutateAsync(values);
    router.replace(safeNext(params.get("next")));
  });

  const error = login.error instanceof ApiError ? login.error.message : login.error ? "We couldn't sign you in. Check your connection." : null;

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to see your plan.">
      {params.get("reset") === "1" && (
        <InlineAlert tone="success" className="mb-4">
          Password updated. Sign in with your new password.
        </InlineAlert>
      )}
      <form noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
        {error && <InlineAlert tone="danger">{error}</InlineAlert>}
        <Field id="email" label="Email" error={errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" inputMode="email" aria-invalid={Boolean(errors.email)} aria-describedby="email-error" {...form.register("email")} />
        </Field>
        <Field id="password" label="Password" error={errors.password?.message}>
          <PasswordInput id="password" autoComplete="current-password" aria-invalid={Boolean(errors.password)} aria-describedby="password-error" {...form.register("password")} />
        </Field>
        <Link href="/forgot-password" className="-mt-2 self-end text-sm font-semibold text-primary">
          Forgot password?
        </Link>
        <Button type="submit" size="lg" block loading={login.isPending} className="mt-2">
          Sign in
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          New to Savora?{" "}
          <Link href="/register" className="font-semibold text-primary">
            Create an account
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
